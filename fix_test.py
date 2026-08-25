with open('raw_test.py', 'r') as f:
    code = f.read()

code = code.replace(
    '        import __main__ as main_module\n\n        old_argv = sys.argv\n        sys.argv = ["password_gen"] + cli_args\n        try:\n            main_module.main()',
    '        import runpy\n\n        old_argv = sys.argv\n        sys.argv = ["password_gen"] + cli_args\n        try:\n            runpy.run_path("__main__.py", run_name="__main__")'
)

code = code.replace(
    '            [sys.executable, "-m", "__main__"] + args,',
    '            [sys.executable, "__main__.py"] + args,'
)

with open('fixed_test.py', 'w') as f:
    f.write(code)
