import unittest
from unlimited.crew_hierarchy import crew_catalog, validate_placement, CREW_GROUPS
from unlimited.junior_factory import catalog, propose_junior

class CrewHierarchyTests(unittest.TestCase):
    def test_visual_roles_and_all_juniors_are_placed(self):
        view=crew_catalog()
        self.assertEqual(view['hierarchy'][-2:], ['junior', 'tool'])
        self.assertEqual(view['orchestration']['engine'], 'T3 / World Commander')
        self.assertFalse(view['execution_authorized'])
        for role in ('CEO','CFO','Conductor','Router','Coordinator','Researcher','Architect',
                     'Verifier','Skeptic','Cynic','Maintainer','Customer Care','Director'):
            self.assertTrue(any(role in roles for roles in CREW_GROUPS.values()),role)
        self.assertEqual(set(view['juniors']),set(catalog()))
        for family in catalog():
            group, role=validate_placement(family)
            self.assertIn(role,CREW_GROUPS[group])
            self.assertEqual(catalog()[family]['parent_role'],role)
            self.assertFalse(catalog()[family]['connected'])
    def test_only_gmail_has_initial_read_transport(self):
        for family in ('slack','outlook','github','cloudflare'):
            self.assertFalse(catalog()[family]['runtime_adapter_available'])
            first=catalog()[family]['operations'][0]['name']
            self.assertEqual(propose_junior(family,'tenant-a',[first]).status,'DRAFT_UNVERIFIED')
        self.assertTrue(catalog()['gmail']['runtime_adapter_available'])

if __name__=='__main__': unittest.main()
