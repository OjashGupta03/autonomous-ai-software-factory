 import string                                                                              +
 import subprocess                                                                          +
 import sys                                                                                 +
                                                                                            +
 import pytest                                                                              +
                                                                                            +
 from cli import parse_args                                                                 +
 from generator import generate_password                                                    +
                                                                                            +
                                                                                            +
 # ---------------------------------------------------------------------------              +
 # Integration tests: full flow from CLI args to generator output                           +
 # ---------------------------------------------------------------------------              +
                                                                                            +
 class TestCliToGeneratorFlow:                                                              +
     """End-to-end tests that verify the complete pipeline:                                 +
     CLI arguments → parse_args → generate_password → output.                               +
     """                                                                                    +
                                                                                            +
     def _run_full_flow(self, cli_args):                                                    +
         """Helper: parse CLI args, generate password, return the result."""                +
         args = parse_args(cli_args)                                                        +
         password = generate_password(                                                      +
             length=args.length,                                                            +
             include_special=args.special,                                                  +
             include_numbers=args.numbers,                                                  +
         )                                                                                  +
         return password                                                                    +
                                                                                            +
     # -- Basic flow tests ---------------------------------------------------              +
                                                                                            +
     def test_basic_flow_default_flags(self):                                               +
         """CLI with only length → password of correct length, letters only."""             +
         password = self._run_full_flow(["12"])                                             +
         assert len(password) == 12                                                         +
         allowed = set(string.ascii_uppercase + string.ascii_lowercase)                     +
         assert all(c in allowed for c in password)                                         +
                                                                                            +
     def test_flow_with_special_flag(self):                                                 +
         """CLI with --special → password may contain special characters."""                +
         password = self._run_full_flow(["32", "--special"])                                +
         assert len(password) == 32                                                         +
         allowed = set(string.ascii_uppercase + string.ascii_lowercase + string.punctuation)+
         assert all(c in allowed for c in password)                                         +
                                                                                            +
     def test_flow_with_numbers_flag(self):                                                 +
         """CLI with --numbers → password may contain digits."""                            +
         password = self._run_full_flow(["32", "--numbers"])                                +
         assert len(password) == 32                                                         +
         allowed = set(string.ascii_uppercase + string.ascii_lowercase + string.digits)     +
         assert all(c in allowed for c in password)                                         +
                                                                                            +
     def test_flow_with_both_flags(self):                                                   +
         """CLI with --special --numbers → full character set."""                           +
         password = self._run_full_flow(["32", "--special", "--numbers"])                   +
         assert len(password) == 32                                                         +
         allowed = set(                                                                     +
             string.ascii_uppercase                                                         +
             + string.ascii_lowercase                                                       +
             + string.digits                                                                +
             + string.punctuation                                                           +
         )                                                                                  +
         assert all(c in allowed for c in password)                                         +
                                                                                            +
     # -- Length boundary tests -----------------------------------------------             +
                                                                                            +
     def test_flow_min_length(self):                                                        +
         """CLI with length=1 → single character password."""                               +
         password = self._run_full_flow(["1"])                                              +
         assert len(password) == 1                                                          +
                                                                                            +
     def test_flow_max_length(self):                                                        +
         """CLI with length=128 → 128 character password."""                                +
         password = self._run_full_flow(["128"])                                            +
         assert len(password) == 128                                                        +
                                                                                            +
     def test_flow_zero_length_raises(self):                                                +
         """CLI with length=0 → generator raises ValueError."""                             +
         with pytest.raises(ValueError, match="between 1 and 128"):                         +
             self._run_full_flow(["0"])                                                     +
                                                                                            +
     def test_flow_negative_length_raises(self):                                            +
         """CLI with negative length → generator raises ValueError."""                      +
         with pytest.raises(ValueError, match="between 1 and 128"):                         +
             self._run_full_flow(["-5"])                                                    +
                                                                                            +
     def test_flow_over_max_length_raises(self):                                            +
         """CLI with length=129 → generator raises ValueError."""                           +
         with pytest.raises(ValueError, match="between 1 and 128"):                         +
             self._run_full_flow(["129"])                                                   +
                                                                                            +
     # -- Character set exclusion tests ---------------------------------------             +
                                                                                            +
     def test_flow_no_special_excludes_punctuation(self):                                   +
         """Without --special, password must not contain punctuation."""                    +
         password = self._run_full_flow(["64", "--numbers"])                                +
         assert not any(c in string.punctuation for c in password)                          +
                                                                                            +
     def test_flow_no_numbers_excludes_digits(self):                                        +
         """Without --numbers, password must not contain digits."""                         +
         password = self._run_full_flow(["64", "--special"])                                +
         assert not any(c in string.digits for c in password)                               +
                                                                                            +
     def test_flow_neither_flag_letters_only(self):                                         +
         """Without either flag, password must be letters only."""                          +
         password = self._run_full_flow(["64"])                                             +
         allowed = set(string.ascii_uppercase + string.ascii_lowercase)                     +
         assert all(c in allowed for c in password)                                         +
                                                                                            +
     # -- Uniqueness test -----------------------------------------------------             +
                                                                                            +
     def test_flow_produces_different_passwords(self):                                      +
         """Multiple invocations with same args should produce different passwords."""      +
         passwords = {                                                                      +
             self._run_full_flow(["16", "--special", "--numbers"])                          +
             for _ in range(10)                                                             +
         }                                                                                  +
         assert len(passwords) == 10                                                        +
                                                                                            +
                                                                                            +
 # ---------------------------------------------------------------------------              +
 # Integration tests: __main__.py entry point (stdout capture)                              +
 # ---------------------------------------------------------------------------              +
                                                                                            +
 class TestMainEntryPoint:                                                                  +
     """Tests that verify __main__.main() correctly wires CLI to generator                  +
     and prints the result to stdout.                                                       +
     """                                                                                    +
                                                                                            +
     def _invoke_main(self, cli_args, capsys):                                              +
         """Helper: temporarily replace sys.argv, call main(), return stdout."""            +
         import __main__ as main_module                                                     +
                                                                                            +
         old_argv = sys.argv                                                                +
         sys.argv = ["password_gen"] + cli_args                                             +
         try:                                                                               +
             main_module.main()                                                             +
         finally:                                                                           +
             sys.argv = old_argv                                                            +
                                                                                            +
         captured = capsys.readouterr()                                                     +
         return captured.out.strip()                                                        +
                                                                                            +
     def test_main_prints_password(self, capsys):                                           +
         """main() should print a non-empty password to stdout."""                          +
         password = self._invoke_main(["12"], capsys)                                       +
         assert len(password) == 12                                                         +
         assert password.isprintable()                                                      +
                                                                                            +
     def test_main_with_special(self, capsys):                                              +
         """main() with --special should produce a password that may include punctuation."""+
         password = self._invoke_main(["32", "--special"], capsys)                          +
         assert len(password) == 32                                                         +
         allowed = set(string.ascii_uppercase + string.ascii_lowercase + string.punctuation)+
         assert all(c in allowed for c in password)                                         +
                                                                                            +
     def test_main_with_numbers(self, capsys):                                              +
         """main() with --numbers should produce a password that may include digits."""     +
         password = self._invoke_main(["32", "--numbers"], capsys)                          +
         assert len(password) == 32                                                         +
         allowed = set(string.ascii_uppercase + string.ascii_lowercase + string.digits)     +
         assert all(c in allowed for c in password)                                         +
                                                                                            +
     def test_main_with_both_flags(self, capsys):                                           +
         """main() with both flags should produce a password from the full set."""          +
         password = self._invoke_main(["32", "--special", "--numbers"], capsys)             +
         assert len(password) == 32                                                         +
         allowed = set(                                                                     +
             string.ascii_uppercase                                                         +
             + string.ascii_lowercase                                                       +
             + string.digits                                                                +
             + string.punctuation                                                           +
         )                                                                                  +
         assert all(c in allowed for c in password)                                         +
                                                                                            +
     def test_main_min_length(self, capsys):                                                +
         """main() with length=1 should print a single character."""                        +
         password = self._invoke_main(["1"], capsys)                                        +
         assert len(password) == 1                                                          +
                                                                                            +
     def test_main_max_length(self, capsys):                                                +
         """main() with length=128 should print a 128-character password."""                +
         password = self._invoke_main(["128"], capsys)                                      +
         assert len(password) == 128                                                        +
                                                                                            +
     def test_main_invalid_length_raises(self, capsys):                                     +
         """main() with length=0 should raise ValueError from generator."""                 +
         with pytest.raises(ValueError, match="between 1 and 128"):                         +
             self._invoke_main(["0"], capsys)                                               +
                                                                                            +
     def test_main_missing_length_exits(self, capsys):                                      +
         """main() with no arguments should exit with error (argparse)."""                  +
         with pytest.raises(SystemExit):                                                    +
             self._invoke_main([], capsys)                                                  +
                                                                                            +
                                                                                            +
 # ---------------------------------------------------------------------------              +
 # Integration tests: subprocess (true end-to-end)                                          +
 # ---------------------------------------------------------------------------              +
                                                                                            +
 class TestSubprocessEndToEnd:                                                              +
     """True end-to-end tests that invoke the application as a subprocess,                  +
     mimicking real user interaction.                                                       +
     """                                                                                    +
                                                                                            +
     def _run_subprocess(self, args):                                                       +
         """Run the app as a subprocess and return (stdout, stderr, returncode)."""         +
         result = subprocess.run(                                                           +
             [sys.executable, "-m", "__main__"] + args,                                     +
             capture_output=True,                                                           +
             text=True,                                                                     +
         )                                                                                  +
         return result.stdout.strip(), result.stderr.strip(), result.returncode             +
                                                                                            +
     def test_subprocess_basic(self):                                                       +
         """Subprocess with length arg should succeed and print a password."""              +
         stdout, stderr, rc = self._run_subprocess(["12"])                                  +
         assert rc == 0                                                                     +
         assert len(stdout) == 12                                                           +
                                                                                            +
     def test_subprocess_with_special(self):                                                +
         """Subprocess with --special should succeed."""                                    +
         stdout, stderr, rc = self._run_subprocess(["32", "--special"])                     +
         assert rc == 0                                                                     +
         assert len(stdout) == 32                                                           +
                                                                                            +
     def test_subprocess_with_numbers(self):                                                +
         """Subprocess with --numbers should succeed."""                                    +
         stdout, stderr, rc = self._run_subprocess(["32", "--numbers"])                     +
         assert rc == 0                                                                     +
         assert len(stdout) == 32                                                           +
                                                                                            +
     def test_subprocess_with_both_flags(self):                                             +
         """Subprocess with both flags should succeed."""                                   +
         stdout, stderr, rc = self._run_subprocess(["32", "--special", "--numbers"])        +
         assert rc == 0                                                                     +
         assert len(stdout) == 32                                                           +
                                                                                            +
     def test_subprocess_min_length(self):                                                  +
         """Subprocess with length=1 should produce single character."""                    +
         stdout, stderr, rc = self._run_subprocess(["1"])                                   +
         assert rc == 0                                                                     +
         assert len(stdout) == 1                                                            +
                                                                                            +
     def test_subprocess_max_length(self):                                                  +
         """Subprocess with length=128 should produce 128 characters."""                    +
         stdout, stderr, rc = self._run_subprocess(["128"])                                 +
         assert rc == 0                                                                     +
         assert len(stdout) == 128                                                          +
                                                                                            +
     def test_subprocess_invalid_length_fails(self):                                        +
         """Subprocess with length=0 should fail (ValueError)."""                           +
         stdout, stderr, rc = self._run_subprocess(["0"])                                   +
         assert rc != 0                                                                     +
         assert "ValueError" in stderr or "length" in stderr.lower()                        +
                                                                                            +
     def test_subprocess_missing_length_fails(self):                                        +
         """Subprocess with no args should fail (argparse error)."""                        +
         stdout, stderr, rc = self._run_subprocess([])                                      +
         assert rc != 0                                                                     +
                                                                                            +
     def test_subprocess_non_integer_length_fails(self):                                    +
         """Subprocess with non-integer length should fail (argparse error)."""             +
         stdout, stderr, rc = self._run_subprocess(["abc"])                                 +
         assert rc != 0                                                                     +
                                                                                            +
     def test_subprocess_output_is_printable(self):                                         +
         """Subprocess output should be printable ASCII."""                                 +
         stdout, stderr, rc = self._run_subprocess(["16", "--special", "--numbers"])        +
         assert rc == 0                                                                     +
         assert stdout.isprintable()                                                        +
                                                                                            +
     def test_subprocess_different_runs_differ(self):                                       +
         """Two subprocess runs with same args should produce different passwords."""       +
         out1, _, rc1 = self._run_subprocess(["16", "--special", "--numbers"])              +
         out2, _, rc2 = self._run_subprocess(["16", "--special", "--numbers"])              +
         assert rc1 == 0 and rc2 == 0                                                       +
         assert out1 != out2

