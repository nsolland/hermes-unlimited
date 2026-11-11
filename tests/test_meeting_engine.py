import unittest
from unlimited.meeting_engine import MeetingEngine, MeetingError, platform_for


class FakeTransport:
    def __init__(self):
        self.calls = []

    def join(self, *, url, display_name):
        self.calls.append(("join", url, display_name))
        return "remote-1"

    def speak(self, *, remote_id, text):
        self.calls.append(("speak", remote_id, text))

    def leave(self, *, remote_id):
        self.calls.append(("leave", remote_id))


class MeetingTests(unittest.TestCase):
    def setUp(self):
        self.adapter = FakeTransport()
        self.engine = MeetingEngine({"teams": self.adapter, "google_meet": self.adapter})
        self.scope = {"tenant_id": "tenant-a", "company_id": "company-a"}
        self.session = self.engine.create(url="https://meet.google.com/abc-defg-hij", **self.scope)

    def test_supported_host_and_rejected_impostors(self):
        self.assertEqual(platform_for("https://teams.microsoft.com/l/meetup-join/x"), "teams")
        for url in ("http://meet.google.com/abc", "https://meet.google.com.evil.test/a",
                    "https://evil.test/teams.microsoft.com", "https://u:p@meet.google.com/a"):
            with self.assertRaises(MeetingError):
                platform_for(url)

    def test_simulated_meeting(self):
        with self.assertRaises(PermissionError):
            self.engine.join(self.session.id, **self.scope)
        self.assertEqual(self.adapter.calls, [])
        self.engine.join(self.session.id, approved=True, **self.scope)
        self.engine.ingest_transcript(self.session.id, speaker="Customer",
                                      text="Send proposal", **self.scope)
        with self.assertRaises(PermissionError):
            self.engine.speak(self.session.id, text="Agreed", **self.scope)
        self.engine.speak(self.session.id, text="I am an AI agent.", approved=True, **self.scope)
        proposal = self.engine.propose_task(self.session.id, description="Prepare quote", **self.scope)
        self.assertFalse(proposal["executed"])
        self.engine.leave(self.session.id, **self.scope)
        self.engine.leave(self.session.id, **self.scope)
        report = self.engine.report(self.session.id, **self.scope)
        self.assertEqual(report["state"], "ended")
        self.assertFalse(report["external_work_verified"])
        self.assertFalse(report["transcript"][0]["trusted_instruction"])
        self.assertEqual([call[0] for call in self.adapter.calls], ["join", "speak", "leave"])

    def test_scope_isolation(self):
        for scope in ({"tenant_id": "tenant-b", "company_id": "company-a"},
                      {"tenant_id": "tenant-a", "company_id": "company-b"}):
            with self.assertRaises(MeetingError):
                self.engine.join(self.session.id, approved=True, **scope)
            with self.assertRaises(MeetingError):
                self.engine.report(self.session.id, **scope)

    def test_state_transitions(self):
        with self.assertRaises(MeetingError):
            self.engine.ingest_transcript(self.session.id, speaker="A", text="B", **self.scope)
        self.engine.join(self.session.id, approved=True, **self.scope)
        with self.assertRaises(MeetingError):
            self.engine.join(self.session.id, approved=True, **self.scope)
        self.engine.leave(self.session.id, **self.scope)
        with self.assertRaises(MeetingError):
            self.engine.propose_task(self.session.id, description="x", **self.scope)

    def test_adapter_unavailable(self):
        with self.assertRaises(MeetingError):
            MeetingEngine({}).create(url="https://meet.google.com/abc-defg-hij", **self.scope)


if __name__ == "__main__":
    unittest.main()
