#!/usr/bin/env python3
# -*- coding: utf-8 -*-


import argparse
import os
import datetime
import re
import shutil
from itertools import permutations


TAG_REGEX = re.compile(r"(?<!\w)@(\w+)")
TODO_REGEX = re.compile(r"\[(.)\]")
FILENAME_REGEX = re.compile(r"[^\w\[\] _-]")
UNTAGGED_TAG = "_untagged"
ENCODING = "utf-8"


class NotebookEntry:
    def __init__(self, notebook, relpath):
        self.notebook = notebook
        self.relpath = relpath
        self.abspath = os.path.join(self.notebook.thepath, relpath)
        self.absfile = self.abspath + self.notebook.fileextension

    def findTags(self):
        result = {}

        if os.path.isfile(self.absfile):
            with open(self.absfile, "r", encoding=self.notebook.theencoding) as f:
                for line in f:
                    for thetag in TAG_REGEX.findall(line):
                        result[thetag] = True
                    for thetodo in TODO_REGEX.findall(line):
                        if thetodo == '*':
                            todoType = "todo_done"
                        elif thetodo == 'x':
                            todoType = "todo_wontdo"
                        elif thetodo == '>':
                            todoType = "todo_waiting"
                        else:
                            todoType = "todo_open"
                        result[todoType] = True

        if UNTAGGED_TAG is not None and len(result) == 0:
            result[UNTAGGED_TAG] = True

        return list(result.keys())

    def removeTags(self, theregex):
        if os.path.isfile(self.absfile):
            filecontent = []
            filechanged = False
            with open(self.absfile, "r", encoding=self.notebook.theencoding) as f:
                for line in f:
                    newline = theregex.sub("", line)
                    #newline = line
                    #for thetag in thefulltags:
                    #    newline = newline.replace(thetag, "")
                    filecontent.append(newline)
                    if line != newline:
                        filechanged = True

            if filechanged:
                with open(self.absfile, "w", encoding=self.notebook.theencoding) as f:
                    for line in filecontent:
                        f.write(line)

    def getNamespace(self):
        return self.relpath.replace("_", " ").replace(os.path.sep, ":")

    def getChildren(self):
        result = {}
        if os.path.isdir(self.abspath):
            for f in os.listdir(self.abspath):
                if not f.startswith(".") and not f.startswith("_") and not f.startswith("00-"):
                    abschild = os.path.join(self.abspath, f)
                    if os.path.isfile(abschild) and f.endswith(self.notebook.fileextension):
                        relchild = os.path.join(self.relpath, f[:-len(self.notebook.fileextension)])
                        if relchild not in result:
                            result[relchild] = NotebookEntry(notebook=self.notebook, relpath=relchild)
                    elif os.path.isdir(abschild):
                        relchild = os.path.join(self.relpath, f)
                        if relchild not in result:
                            result[relchild] = NotebookEntry(notebook=self.notebook, relpath=relchild)
        return result.values()


class Notebook:
    def __init__(self, thepath, fileextension, theencoding=ENCODING):
        self.thepath = thepath
        self.fileextension = fileextension
        self.theencoding = theencoding
        self.root = NotebookEntry(self, relpath="")

    def getRoot(self):
        return self.root

    def _findAllTags(self, notebookEntry, tagDict):
        tagDict[notebookEntry] = notebookEntry.findTags()
        for thechild in notebookEntry.getChildren():
            self._findAllTags(notebookEntry=thechild, tagDict=tagDict)

    def findAllTags(self):
        tagDict = {}
        self._findAllTags(notebookEntry=self.root, tagDict=tagDict)
        return tagDict


def tagTree(tagDict):
    result = {"tags": {}, "entries": []}
    for k, v in tagDict.items():
        for p in permutations(v):
            currfolder = result
            for relfolder in p:
                if relfolder not in currfolder["tags"]:
                    currfolder["tags"][relfolder] = {"tags": {}, "entries": []}
                currfolder = currfolder["tags"][relfolder]
            currfolder["entries"].append(k)

    return result


def symlinkTagTree(notebook, reltagsdir, reldir, tagTree):
    for theentry in tagTree["entries"]:
        if os.path.isfile(theentry.absfile):
            abstagsdir = os.path.join(notebook.thepath, reltagsdir, reldir)
            thedst = os.path.join(abstagsdir, theentry.relpath.replace("/", ".") + notebook.fileextension)
            if not os.path.exists(thedst):
                os.makedirs(abstagsdir, exist_ok=True)
                os.symlink(theentry.absfile, thedst)
    for k, v in tagTree["tags"].items():
        thechilddir = os.path.join(reldir, FILENAME_REGEX.sub("_", k))
        symlinkTagTree(notebook=notebook, reltagsdir=reltagsdir, reldir=thechilddir, tagTree=v)


def writeTagTreeMarkdown(f, tagTree, fileextension, depth=0):
    for theentry in sorted(tagTree["entries"], key=lambda x: x.relpath):
        f.write(("    " * depth) + "- [](./" + theentry.relpath + ")\n")
    for k, v in sorted(tagTree["tags"].items()):
        f.write("\n" + ("    " * depth) + "- **" + k + "**\n")
        writeTagTreeMarkdown(f=f, tagTree=v, fileextension=fileextension, depth=depth+1)


def writeTagTreeZIM(f, tagTree, fileextension, depth=0):
    for theentry in sorted(tagTree["entries"], key=lambda x: x.relpath):
        f.write(("\t" * depth) + "* [[:" + theentry.getNamespace() + "]]\n")
    for k, v in sorted(tagTree["tags"].items()):
        f.write("\n" + ("\t" * depth) + "* **" + k + "**\n")
        writeTagTreeZIM(f=f, tagTree=v, fileextension=fileextension, depth=depth+1)


def flattenTagDict(tagDict):
    tagFiles = {}
    for k, v in tagDict.items():
        for tag in v:
            if tag not in tagFiles:
                tagFiles[tag] = []
            tagFiles[tag].append(k)

    return tagFiles


def makeZIMHeader(thetitle):
    now = datetime.datetime.now()
    return "Content-Type: text/x-zim-wiki\nWiki-Format: zim 0.6\nCreation-Date: " + now.strftime("%Y-%m-%dT%H:%M:%S") + "+02:00\n\n====== " + thetitle + " ======\n**" + now.strftime("%Y-%m-%d %H:%M:%S") + "**\n\n"


if __name__ == "__main__":
    argParse = argparse.ArgumentParser()
    argParse.add_argument("--notebookpath", required=True)
    argParse.add_argument("--mode", required=True)
    argParse.add_argument("--removeTagRegex")
    argParse.add_argument("--fileextension", default=".txt")
    argParse.add_argument("--reltagsdir", default="00-Tags")
    argParse.add_argument("--reltagsfile", default="00-Tags.md")
    argParse.add_argument("--fileformat", default="md")
    argParse.add_argument("--includeUntagged", action="store_const", const=True, default=False)
    args = argParse.parse_args()

    notebook = Notebook(thepath=args.notebookpath, fileextension=args.fileextension)
    tagDict = notebook.findAllTags()

    if args.mode == "tagsfile":
        theTagTree = tagTree(tagDict)
        if not args.includeUntagged:
            theTagTree["tags"].pop("_untagged", None)
        tagsFile = os.path.join(args.notebookpath, args.reltagsfile)
        with open(tagsFile, "w", encoding=ENCODING) as f:
            if args.fileformat == "md":
                f.write("# Tags\n\n")
                writeTagTreeMarkdown(f=f, tagTree=theTagTree, fileextension=args.fileextension)
            elif args.fileformat == "zim":
                f.write(makeZIMHeader(thetitle="Tags"))
                writeTagTreeZIM(f=f, tagTree=theTagTree, fileextension=args.fileextension)
            else:
                raise Exception("unknown file format")

    elif args.mode == "flattagsfile":
        flatTagDict = flattenTagDict(tagDict=tagDict)
        if not args.includeUntagged:
            flatTagDict.pop("_untagged", None)
        tagsFile = os.path.join(args.notebookpath, args.reltagsfile)
        if args.fileformat == "md":
            with open(tagsFile, "w", encoding=ENCODING) as f:
                f.write("# Tags\n")
                for k, v in sorted(flatTagDict.items()):
                    f.write("\n## " + k + "\n")
                    for theentry in sorted(v):
                        f.write("- [](" + theentry.relpath + ")\n")

        elif args.fileformat == "zim":
            with open(tagsFile, "w", encoding=ENCODING) as f:
                f.write(makeZIMHeader(thetitle="Tags"))
                for k, v in sorted(flatTagDict.items()):
                    f.write("\n===== " + k + " =====\n")
                    for theentry in sorted(v):
                        f.write("* [[:" + theentry.getNamespace() + "]]\n")
        else:
            raise Exception("unknown file format")

    elif args.mode == "symlink":
        theTagTree = tagTree(tagDict)
        absdir = os.path.join(args.notebookpath, args.reltagsdir)
        if os.path.exists(absdir):
            shutil.rmtree(absdir)
        symlinkTagTree(notebook=notebook, reldir="", reltagsdir=args.reltagsdir, tagTree=theTagTree)

    elif args.mode == "flatsymlink":
        flatTagDict = flattenTagDict(tagDict=tagDict)
        absdir = os.path.join(args.notebookpath, args.reltagsdir)
        if os.path.exists(absdir):
            shutil.rmtree(absdir)

        for k, v in flatTagDict.items():
            abstagsdir = os.path.join(absdir, FILENAME_REGEX.sub("_", k))
            os.makedirs(abstagsdir, exist_ok=False)

            for theentry in v:
                thedst = os.path.join(abstagsdir, theentry.relpath.replace("/", ".") + args.fileextension)
                if not os.path.exists(thedst):
                    os.symlink(theentry.absfile, thedst)

    elif args.mode == "remove":
        if len(args.removeTagRegex) == 0:
            raise Exception("no tagname regex provided")
        fullRemoveRegex = re.compile(r"(?<!\w)@" + args.removeTagRegex + r"\b")
        removeRegex = re.compile(args.removeTagRegex)

        for k, v in tagDict.items():
            matchingTags = []
            for thetag in v:
                if removeRegex.match(thetag) is not None:
                    k.removeTags(theregex=fullRemoveRegex)
                    break
            #        matchingTags.append("@" + thetag)
            #if len(matchingTags) != 0:
            #    k.removeTags(theregex=fullRemoveRegex)

    else:
        raise Exception("unknown mode")
