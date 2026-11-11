"""Meeting orchestration: explicit operator-approved audio and no implicit task execution."""
from dataclasses import dataclass, field
from enum import Enum
from threading import RLock
from typing import Protocol
from urllib.parse import urlparse
import uuid


class MeetingState(str, Enum):
    CREATED = "created"
    JOINED = "joined"
    ENDED = "ended"


class MeetingError(ValueError):
    pass


class MeetingTransport(Protocol):
    def join(self, *, url: str, display_name: str) -> str: ...
    def speak(self, *, remote_id: str, text: str) -> None: ...
    def leave(self, *, remote_id: str) -> None: ...


@dataclass
class Session:
    id: str
    tenant_id: str
    company_id: str
    platform: str
    url: str
    display_name: str
    state: MeetingState = MeetingState.CREATED
    remote_id: str | None = None
    transcript: list[dict] = field(default_factory=list)
    actions: list[dict] = field(default_factory=list)


def platform_for(url: str) -> str:
    parsed = urlparse(url)
    host = (parsed.hostname or "").lower()
    if parsed.scheme != "https" or parsed.username or parsed.password:
        raise MeetingError("INVALID_MEETING_URL")
    if host == "meet.google.com":
        return "google_meet"
    if host in {"teams.microsoft.com", "teams.live.com"}:
        return "teams"
    raise MeetingError("UNSUPPORTED_MEETING_HOST")


class MeetingEngine:
    """Provider-neutral transport coordination, scoped by tenant and company.

    No production meeting connectivity exists until a real transport is supplied.
    A human/operator explicitly grants join and speech. Transcripts are data,
    never instructions or execution authorization.
    """
    def __init__(self, adapters: dict[str, MeetingTransport]):
        self._adapters = dict(adapters)
        self._sessions: dict[str, Session] = {}
        self._lock = RLock()

    def create(self, *, tenant_id: str, company_id: str, url: str,
               display_name: str = "Hermes Unlimited AI Agent") -> Session:
        if not all(isinstance(v, str) and v.strip() for v in (tenant_id, company_id, display_name)):
            raise MeetingError("MISSING_SCOPE")
        if len(display_name) > 100:
            raise MeetingError("INVALID_DISPLAY_NAME")
        platform = platform_for(url)
        if platform not in self._adapters:
            raise MeetingError("ADAPTER_UNAVAILABLE")
        session = Session(str(uuid.uuid4()), tenant_id, company_id, platform, url, display_name)
        with self._lock:
            self._sessions[session.id] = session
        return session

    def _owned(self, meeting_id: str, tenant_id: str, company_id: str) -> Session:
        session = self._sessions.get(meeting_id)
        if not session or (session.tenant_id, session.company_id) != (tenant_id, company_id):
            raise MeetingError("MEETING_NOT_FOUND")
        return session

    def join(self, meeting_id: str, *, tenant_id: str, company_id: str,
             approved: bool = False) -> Session:
        if approved is not True:
            raise PermissionError("JOIN_REQUIRES_APPROVAL")
        with self._lock:
            s = self._owned(meeting_id, tenant_id, company_id)
            if s.state != MeetingState.CREATED:
                raise MeetingError("INVALID_STATE")
            remote_id = self._adapters[s.platform].join(url=s.url, display_name=s.display_name)
            if not isinstance(remote_id, str) or not remote_id:
                raise MeetingError("INVALID_REMOTE_ID")
            s.remote_id = remote_id
            s.state = MeetingState.JOINED
            return s

    def ingest_transcript(self, meeting_id: str, *, tenant_id: str, company_id: str,
                          speaker: str, text: str) -> None:
        with self._lock:
            s = self._owned(meeting_id, tenant_id, company_id)
            if s.state != MeetingState.JOINED:
                raise MeetingError("INVALID_STATE")
            if not isinstance(text, str) or not isinstance(speaker, str):
                raise MeetingError("INVALID_TRANSCRIPT")
            s.transcript.append({"speaker": speaker[:100], "text": text[:10000],
                                 "trusted_instruction": False})

    def speak(self, meeting_id: str, *, tenant_id: str, company_id: str,
              text: str, approved: bool = False) -> None:
        if approved is not True:
            raise PermissionError("SPEECH_REQUIRES_APPROVAL")
        if not isinstance(text, str) or not text.strip() or len(text) > 4000:
            raise MeetingError("INVALID_SPEECH")
        with self._lock:
            s = self._owned(meeting_id, tenant_id, company_id)
            if s.state != MeetingState.JOINED or not s.remote_id:
                raise MeetingError("INVALID_STATE")
            self._adapters[s.platform].speak(remote_id=s.remote_id, text=text)
            s.actions.append({"type": "spoken", "text": text})

    def propose_task(self, meeting_id: str, *, tenant_id: str, company_id: str,
                     description: str) -> dict:
        if not isinstance(description, str) or not description.strip() or len(description) > 2000:
            raise MeetingError("INVALID_TASK")
        with self._lock:
            s = self._owned(meeting_id, tenant_id, company_id)
            if s.state != MeetingState.JOINED:
                raise MeetingError("INVALID_STATE")
            proposal = {"id": str(uuid.uuid4()), "description": description,
                        "status": "PROPOSED_UNAUTHORIZED", "executed": False}
            s.actions.append(proposal)
            return proposal

    def leave(self, meeting_id: str, *, tenant_id: str, company_id: str) -> Session:
        with self._lock:
            s = self._owned(meeting_id, tenant_id, company_id)
            if s.state == MeetingState.ENDED:
                return s
            if s.state == MeetingState.JOINED and s.remote_id:
                self._adapters[s.platform].leave(remote_id=s.remote_id)
            s.state = MeetingState.ENDED
            return s

    def report(self, meeting_id: str, *, tenant_id: str, company_id: str) -> dict:
        with self._lock:
            s = self._owned(meeting_id, tenant_id, company_id)
            return {"meeting_id": s.id, "platform": s.platform, "state": s.state.value,
                    "transcript": list(s.transcript), "actions": list(s.actions),
                    "external_work_verified": False}
