 from cli import parse_args                                    +


 class TestRequiredLengthArgument:                             +
     """Tests for the required 'length' positional argument."""+

     def test_length_parsed_correctly(self):                   +
         args = parse_args(["12"])                             +
         assert args.length == 12                              +

     def test_length_zero(self):                               +
         args = parse_args(["0"])                              +
         assert args.length == 0                               +

     def test_length_large_value(self):                        +
         args = parse_args(["100"])                            +
         assert args.length == 100                             +

     def test_missing_length_raises_error(self):               +
         with pytest.raises(SystemExit):                       +
             parse_args([])                                    +


 class TestOptionalSpecialFlag:                                +
     """Tests for the optional '--special' flag."""            +

     def test_special_default_false(self):                     +
         args = parse_args(["12"])                             +
         assert args.special is False                          +

     def test_special_flag_true(self):                         +
         args = parse_args(["12", "--special"])                +
         assert args.special is True                           +


 class TestOptionalNumbersFlag:                                +
     """Tests for the optional '--numbers' flag."""            +

     def test_numbers_default_false(self):                     +
         args = parse_args(["12"])                             +
         assert args.numbers is False                          +

     def test_numbers_flag_true(self):                         +
         args = parse_args(["12", "--numbers"])                +
         assert args.numbers is True                           +


 class TestCombinedFlags:                                      +
     """Tests for combining multiple flags."""                 +

     def test_both_flags_true(self):                           +
         args = parse_args(["12", "--special", "--numbers"])   +
         assert args.length == 12                              +
         assert args.special is True                           +
         assert args.numbers is True                           +

     def test_special_only(self):                              +
         args = parse_args(["8", "--special"])                 +
         assert args.length == 8                               +
         assert args.special is True                           +
         assert args.numbers is False                          +

     def test_numbers_only(self):                              +
         args = parse_args(["16", "--numbers"])                +
         assert args.length == 16                              +
         assert args.special is False                          +
         assert args.numbers is True                           +


 class TestErrorHandling:                                      +
     """Tests for invalid input handling."""                   +

     def test_non_integer_length_raises_error(self):           +
         with pytest.raises(SystemExit):                       +
             parse_args(["abc"])                               +

     def test_float_length_raises_error(self):                 +
         with pytest.raises(SystemExit):                       +
             parse_args(["12.5"])                              +

     def test_negative_length_accepted_by_parser(self):        +
         # argparse with type=int accepts negative numbers     +
         args = parse_args(["-5"])                             +
         assert args.length == -5                              +

     def test_empty_string_length_raises_error(self):          +
         with pytest.raises(SystemExit):                       +
             parse_args([""])

