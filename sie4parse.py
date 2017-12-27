#!/usr/bin/python3
#
# This is a parser for the SIE4 format, an accounting interchange format
# widely used in Sweden. This program was created to handle files from
# a very specific source and convert them to something useful, so it may
# not work well or at all for other purposes.
#

import argparse
import csv
import logging
import shlex

sortByDate = False

def writeCsv(data, outfile):
    log = logging.getLogger("csv")
    w = csv.writer(outfile, dialect="excel")
    
    # Write the account number and names as two header lines
    accountNumbers = sorted(data.accountNames.keys())
    w.writerow(["#", "date", "text"] + accountNumbers)
    w.writerow(["", "", ""] + [data.accountNames[n] for n in accountNumbers])

    for entry in sorted(data.entries):
        row = [entry.number, parseDate(entry.date), entry.text]
        row += [""] * len(accountNumbers)
        for (account, amount) in entry.entries.items():
            accountCol = accountNumbers.index(account)
            row[accountCol + 3] = amount
        w.writerow(row)

def writeSie(data, outfile):
    log = logging.getLogger("sie")

    # Write the headers
    for h, fields in data.headers.items():
        outfile.write("#%s %s\n" % (h, " ".join(['"%s"' % f for f in fields])))

    # Write the account list
    for number, name in data.accountNames.items():
        outfile.write('#KONTO %d "%s"\n' % (number, name))

    # Write the verification list
    for entry in sorted(data.entries):
        outfile.write('#VER "%s" %d %s "%s"\n' % (entry.series, entry.number, entry.date, entry.text))
        outfile.write("{\n")
        for account, amount in entry.entries.items():
            outfile.write("#TRANS %d {} %s\n" % (account, amount))
        outfile.write("}\n")
        outfile.write("\n")

def parseDate(s):
    return "%s-%s-%s" % (s[0:4], s[4:6], s[6:8])

class Entry(object):
    def __init__(self):
        self.entries = {}

    def addTransaction(self, account, amount):
        assert(account not in self.entries)
        self.entries[account] = amount

    def __lt__(self, b):
        if sortByDate and self.date != b.date:
            return self.date < b.date
        return self.number < b.number

    def __str__(self):
        return "%d %s %s: %s" % (self.number, self.date, self.text, self.entries)

class FileData(object):
    def __init__(self):
        self.log = logging.getLogger("sieparse")
        
        # Account number to name mapping (int=string dict)
        self.accountNames = {}
        
        # Various unparsed header fields
        self.headers = {}
        
        # Accounting entries (verifications)
        self.entries = []

    def parseFile(self, infilename):
        # Open file with codepage 437 encoding (#FORMAT "PC8")
        with open(infilename, 'r', encoding="cp437") as f:
            for line in f:
                self.parseLine(line)

    def parseLine(self, line):
        split = shlex.split(line)
        if len(split) == 0:
            return
        #self.log.info("Line: %s" % split)
        if split[0].startswith("#"):
            self.parseLabel(split[0][1:], split[1:])
        elif split[0] == "{":
            assert(len(split) == 1)
            self.pushBracket()
        elif split[0] == "}":
            assert(len(split) == 1)
            self.popBracket()

    def parseLabel(self, label, fields):
        if label == "KONTO":
            self.accountNames[int(fields[0])] = fields[1]
        elif label == "VER":
            self.parseVer(fields)
        elif label == "TRANS":
            self.parseTrans(fields)
        else:
            self.headers[label] = fields

    def pushBracket(self):
        pass

    def popBracket(self):
        pass

    def parseVer(self, fields):
        """Parse a ver (an accounting entry)"""
        # Fields are: series, number, date, ver text, reg date, sign
        # This field is followed by TRANS fields in brackets
        e = Entry()
        e.series = fields[0]
        e.number = int(fields[1])
        e.date = fields[2]
        e.text = fields[3]
        self.entries.append(e)

    def parseTrans(self, fields):
        """Parse a transaction between accounts"""
        # Note: the transactions are within brackets in a #VER entry,
        # and ideally we should keep track of that. However, we seem
        # to get away with just referring to the last seen #VER.
        
        # Add this data to the last #VER entry
        e = self.entries[-1]
        e.addTransaction(int(fields[0]), float(fields[2]))

if __name__ == "__main__":
    logging.basicConfig(level=logging.DEBUG)
    
    parser = argparse.ArgumentParser(description="SIE4 file parser")
    parser.add_argument(dest="infile", nargs=1, metavar="FILENAME",
                        help="Input SIE4 file")
    parser.add_argument("--csv", metavar="FILENAME",
                        help="Output CSV file")
    parser.add_argument("--si", metavar="FILENAME",
                        help="Output an SIE4 file")
    parser.add_argument("--sort-date", action="store_true",
                        help="Sort by date instead of number")

    args = parser.parse_args()

    data = FileData()
    data.parseFile(args.infile[0])

    sortByDate = args.sort_date

    if args.csv:
        with open(args.csv, "w") as f:
            writeCsv(data, f)

    if args.si:
        with open(args.si, "w", encoding="cp437") as f:
            writeSie(data, f)

    if not args.csv and not args.si:
        logging.warning("No output file selected")
