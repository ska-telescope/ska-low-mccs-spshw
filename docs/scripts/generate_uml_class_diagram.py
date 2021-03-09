#!/usr/bin/env python

"""
https://github.com/jose-caballero/genUML/blob/master/external/gen.py
"""
import re
import sys
from optparse import OptionParser
from os.path import splitext, basename


class UmlClassFigGenerator(object):
    def __init__(self, file_list, options):
        self.file_list = file_list
        # notice: parent class was like that: "parent_class.ClassName2"
        self.re_class_def = re.compile(r"^class\s+([\w\d]+)\(\s*([\w\d\._]+)\s*\):")
        self.re_class_def_noparent = re.compile(r"^class\s+([\w\d]+)\s*:")

        self.re_method_def = re.compile(r"^\s+def (\w+)\(.*\):")
        self.re_member_def = re.compile(r"^\s+self.([_\w]+)\s*=")
        # CamelCase regexp
        self.re_class_name_call = re.compile(r"((:?[A-Z]+[a-z0-9]+)+)\(.*\)")
        self.re_ignore_line = re.compile(r"^\s*(:?$|#|raise|print)")
        self.re_private_name = re.compile(r"^_[\w\d_]+")
        self.re_special_name = re.compile(r"^__[\w_]+__")

        self.parent_dic = {}  # class inheritance relation
        self.relate_dic = {}  # other class relation
        self.class_list = []  # list of class name
        self.ignore_parents = ["object", ""]

        self.class_name = None
        self.member_dic = {}  # list of member val name
        self.method_dic = {}  # list of method val name
        self._options = options
        self._out = None

    def _check_name_visibility(self, name):
        if self.re_special_name.match(name):
            return "+" + name
        elif self.re_private_name.match(name):
            return "-" + name
        else:
            return "+" + name

    def _check_line_class_def(self, class_name, parent_class_name):
        if "." in parent_class_name:
            # if written by "package.classname" format
            pcn_list = parent_class_name.split(".")
            pkg = pcn_list[0:-1]
            cls = pcn_list[-1]
            # print(f"## pkg={pkg}, cls={cls}")
            parent_class_name = cls
        if class_name in self.class_list:
            return  # is there multiple definition??
        self.class_name = class_name
        self.member_dic[class_name] = []
        self.method_dic[class_name] = []
        self.relate_dic[class_name] = []
        self.class_list.append(class_name)
        if self._out:
            self._out.write(f"{self._indent}class {class_name}\n")
        print(f"{self._indent}class {class_name}")
        if parent_class_name not in self.ignore_parents:
            self.parent_dic[class_name] = parent_class_name
            # print(f"  {parent_class_name} <|-- {class_name}")

    def _check_line_method_def(self, method_name):
        method_name = self._check_name_visibility(method_name)
        if method_name not in self.method_dic[self.class_name]:
            self.method_dic[self.class_name].append(method_name)
            if self._out:
                self._out.write(f"{self._indent}{self.class_name} : {method_name}()\n")
            print(f"{self._indent}{self.class_name} : {method_name}()")

    def _check_line_member_def(self, member_name):
        member_name = self._check_name_visibility(member_name)
        if member_name not in self.member_dic[self.class_name]:
            self.member_dic[self.class_name].append(member_name)

    def _check_line_class_relation(self, called_class_name):
        # print(f"#call: {called_class_name} in {class_name}")
        if called_class_name not in self.relate_dic[self.class_name]:
            self.relate_dic[self.class_name].append(called_class_name)

    def _read_file(self, file_name):
        for line in open(file_name, "r"):
            if self.re_ignore_line.match(line):
                # print(f"# ignored: {line}")
                continue

            # def class
            m_cdef = self.re_class_def.match(line)
            if m_cdef:
                self._check_line_class_def(m_cdef.group(1), m_cdef.group(2))
                continue
            m_cdef_noparent = self.re_class_def_noparent.match(line)
            if m_cdef_noparent:
                self._check_line_class_def(m_cdef_noparent.group(1), "")
                continue

            # def method
            m_mtd = self.re_method_def.match(line)
            if m_mtd and self.class_name:
                self._check_line_method_def(m_mtd.group(1))
                continue

            # member val
            m_mval = self.re_member_def.match(line)
            if m_mval and self.class_name:
                self._check_line_member_def(m_mval.group(1))

            # instance generate
            m_call = self.re_class_name_call.search(line)
            if m_call and self.class_name:
                self._check_line_class_relation(m_call.group(1))

    def _pre_read_file(self, file_name):
        # print(f"## file_name={file_name}")
        self.class_name = None
        self.member_dic = {}
        if not options.no_package:
            root, ext = splitext(basename(file_name))
            if self._out:
                self._out.write(f"package {root} {{\n")
            print(f"package {root} {{")

    def _post_read_file(self):
        # print member list
        for cname, mlist in self.member_dic.items():
            for member_name in mlist:
                if self._out:
                    self._out.write(f"{self._indent}{cname} : {member_name}\n")
                print(f"{self._indent}{cname} : {member_name}")
        if not options.no_package:
            if self._out:
                self._out.write("{\n")
            print("}")  # end package
        if self._out:
            self._out.write("\n")
        print("\n")

    def _post_read_files(self):
        # parent class
        for ccls, pcls in self.parent_dic.items():
            if self._out:
                self._out.write(f"{pcls} <|-- {ccls}\n")
            print(f"{pcls} <|-- {ccls}")
        # relation of class
        for cls1, clist in self.relate_dic.items():
            for called_class_name in clist:
                if called_class_name in self.class_list and cls1 != called_class_name:
                    # print class which aws defined in files
                    if self._out:
                        self._out.write(f"{cls1} -- {called_class_name}\n")
                    print(f"{cls1} -- {called_class_name}")

    def _read_files(self):
        if self._out:
            self._out.write("@startuml\n")
        print("@startuml")
        for file_name in self.file_list:
            self._pre_read_file(file_name)
            self._read_file(file_name)
            self._post_read_file()
        self._post_read_files()
        if self._out:
            self._out.write("@enduml\n")
        print("@enduml")

    def gen_fig(self):
        if options.filename:
            self._out = open(options.filename, "w")
        self._indent = "" if options.no_package else "  "
        self._read_files()


if __name__ == "__main__":
    usage = "usage: %prog [options] /foo/bar/*.py"
    parser = OptionParser(usage=usage)
    parser.add_option(
        "-o",
        "--output",
        dest="filename",
        help="write generated uml to FILE",
        metavar="FILE",
    )
    parser.add_option(
        "-n",
        "--no-package",
        default=False,
        action="store_true",
        help="Do not generate package information",
    )
    (options, args) = parser.parse_args()
    print(options)

    if not args:
        print(usage)
        exit(1)
    class_fig_gen = UmlClassFigGenerator(args, options)
    class_fig_gen.gen_fig()
