

 def parse_args(args=None):                                          +
     """Parse command-line arguments for password generation.        +

     Args:                                                           +
         args: Optional list of argument strings (for testing).      +
               If None, sys.argv is used.                            +

     Returns:                                                        +
         argparse.Namespace with attributes:                         +
             - length (int): Required password length.               +
             - special (bool): Whether to include special characters.+
             - numbers (bool): Whether to include digits.            +
     """                                                             +
     parser = argparse.ArgumentParser(                               +
         description="Generate a random password."                   +
     )                                                               +

     parser.add_argument(                                            +
         "length",                                                   +
         type=int,                                                   +
         help="Length of the generated password."                    +
     )                                                               +

     parser.add_argument(                                            +
         "--special",                                                +
         action="store_true",                                        +
         default=False,                                              +
         help="Include special characters in the password."          +
     )                                                               +

     parser.add_argument(                                            +
         "--numbers",                                                +
         action="store_true",                                        +
         default=False,                                              +
         help="Include digits in the password."                      +
     )                                                               +

     return parser.parse_args(args)                                  +


 if __name__ == "__main__":                                          +
     args = parse_args()                                             +
     print(f"Length: {args.length}")                                 +
     print(f"Special characters: {args.special}")                    +
     print(f"Numbers: {args.numbers}")

