import os, sys, tempfile, unittest
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))
from utils import shortcut as sc
from utils import settings as cfg

class ShortcutTests(unittest.TestCase):
    def setUp(self):
        d = tempfile.mkdtemp()
        cfg.settings_path = lambda: os.path.join(d, "settings.json")
        self.calls, self.msgs = [], []
    def run_setup(self, ask=True, ok=True, **kw):
        def runner(exe):
            self.calls.append(exe); return (ok, "" if ok else "boom")
        asked = []
        sc.setup(lambda: asked.append(1) or ask, self.msgs.append, runner=runner,
                 frozen=kw.get("frozen", True), exe=r"C:\MUNIM\app\MUNIM.exe",
                 is_windows=kw.get("is_windows", True))
        return asked

    def test_noop_when_not_built_exe(self):
        self.assertEqual(self.run_setup(frozen=False), [])
        self.assertEqual(self.run_setup(is_windows=False), [])
        self.assertEqual(self.calls, [])

    def test_yes_creates_and_remembers(self):
        self.assertEqual(len(self.run_setup(ask=True)), 1)
        self.assertEqual(self.calls, [r"C:\MUNIM\app\MUNIM.exe"])
        self.assertTrue(cfg.load_settings()["desktop_shortcut"])

    def test_no_is_remembered_and_never_asked_again(self):
        self.run_setup(ask=False)
        self.assertEqual(self.calls, [])
        self.assertEqual(self.run_setup(ask=True), [])
        self.assertEqual(self.calls, [])

    def test_failure_notifies_and_stops_asking(self):
        self.run_setup(ask=True, ok=False)
        self.assertEqual(len(self.msgs), 1)
        self.assertEqual(self.run_setup(), [])

    def test_script_has_no_user_text_injected(self):
        self.assertIn("$env:MUNIM_EXE", sc.PS_SCRIPT)

if __name__ == "__main__":
    unittest.main()
