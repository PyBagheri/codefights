class Main:
    def testfunc1(self, *args):
        arg_list = {}
        for i in range(len(args)):
            arg_list[i] = args[i]
        return arg_list