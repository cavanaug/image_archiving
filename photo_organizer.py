#!/usr/bin/env python3
#from __future__ import print_function
import argparse
import sys
import os
import os.path
import time
import re
import exifread
import shutil
import glob

import traceback
import logging

from pathlib import Path

from autologging import logged, TRACE, traced


debug = False

counter = 0

modelAlias = {
    #
    #  SmartPhones
    #
    "iPhone": "IOS",
    "iPhone 3G": "IOS",
    "iPhone 4": "IOS",
    "iPhone 4S": "IOS",
    "iPhone 5": "IOS",
    "iPhone 5S": "IOS",
    "iPhone 5s": "IOS",
    "iPhone 6": "IOS",
    "iPhone 6s Plus": "IOS",
    "iPhone 6 Plus": "IOS",
    "iPhone 6S": "IOS",
    "iPhone 6s": "IOS",
    "iPhone SE": "IOS",
    "iPad mini": "IOS",

    "Nexus 5": "DROID",
    "Nexus 5X": "DROID",

    #
    #  Modern Cameras
    #
    "Canon EOS 10D": "10D",
    "Canon EOS 20D": "20D",
    "Canon EOS 30D": "30D",
    "Canon EOS 40D": "40D",
    "Canon EOS 50D": "50D",
    "Canon EOS 60D": "60D",
    "Canon EOS 70D": "70D",
    "Canon EOS 7D": "7D",

    "Canon EOS-1D X Mark II": "1D",
    "Canon EOS 5D Mark III": "5D",

    "EX-S600": "MISC",
    "HP ojj3600": "MISC",
    "HP ojj3600": "MISC",

    "Canon EOS REBEL T3i": "EOS",  # Petter?
    "Canon EOS DIGITAL REBEL XTi": "EOS",  # Petter?
    "Canon EOS DIGITAL REBEL": "EOS",  # Petter?

    "Canon PowerShot S200": "PSHOT",
    "Canon PowerShot SX200 IS": "PSHOT",
    "Canon PowerShot SD550": "PSHOT",
    "Canon PowerShot SD630": "PSHOT",
    "Canon PowerShot SD500": "PSHOT",
    "Canon PowerShot SD800 IS": "PSHOT",
    "Canon PowerShot SD1100 IS": "PSHOT",
    "Canon PowerShot G3": "PSHOT",
    "Canon PowerShot G1 X": "PSHOT",
    "Canon PowerShot A70": "PSHOT",
    "Canon PowerShot SD1200 IS": "PSHOT",
    "Canon PowerShot A3100 IS": "PSHOT",
    "Canon PowerShot SD890 IS": "PSHOT",
    "Canon PowerShot S2 IS": "PSHOT",
    "Canon PowerShot SX20 IS": "PSHOT",
    "Canon PowerShot A710 IS": "PSHOT",
    "Canon PowerShot S3 IS": "PSHOT",
    "Canon PowerShot SD700 IS": "PSHOT",
    "Canon PowerShot S50": "PSHOT",
    "Canon PowerShot G7": "PSHOT",
    "Canon PowerShot ELPH 300 HS": "PSHOT",
    #
    #  Old or Non-Canon Cameras
    #
    "HP PhotoSmart R607 (V01.00)": "R607",  # Granny
    "HP PhotoSmart R607 (V01.00)d": "R607",  # Granny
    "Vivicam 5299": "VIV",  # Kaitlyn
    "FinePix2400Zoom": "FZ",  # Johns Ancient
    #
    #  "Other" category
    #
    "P2020": "MISC",
    "DMC-FZ28": "MISC",
    "FinePix F10": "MISC",  # Jimmy?
    "KODAK DX3900 ZOOM DIGITAL CAMERA": "MISC",  # Jimmy?
    "MX-2700": "MISC",  # Jimmy?
    "DMC-ZS6": "MISC",  # Jimmy?
    "DMC-LX2": "MISC",  # Jimmy?
    "DMC-ZS7": "MISC",  # Jimmy?
    "PENTAX Optio S60": "MISC",  # Jimmy?
    "DSC-W220": "MISC",  # Jimmy?
    "BlackBerry 8320": "MISC",  # Jimmy?
    "HP pst3300": "MISC",  # Jimmy?
    "NIKON D80": "MISC",  # Jimmy?
    "NIKON D600": "MISC",  # Jimmy?
    "NIKON D700": "MISC",  # Jimmy?
    "NIKON D200": "MISC",  # Jimmy?
    "QSS": "MISC",  # Jimmy?
    "FinePix Z10fd": "MISC",  # Jimmy?
    "MG6100 series": "MISC",
    "DMC-LX5": "MISC",
    #
    #  Misc/Unknown Cameras
    #
    "Unknown": "UNK",
}

def getModelAlias(model):
    if args.use_unknown:
        modelShort = "UNK"
    if model in modelAlias:
        modelShort = modelAlias[model]
    return modelShort


#
# Provide a new file name that matches my PERSONAL PREFERENCE for image filenames
#
# Pass it the full path to the source image and it will return the basename of the newfilename to be used
#
# Desired behavior is something like these examples:
#    IMG_0429JPG -> YYYYMMDD-HHMMSSX-ZZZ.JPG
#    IMG_0429_edited.JPG -> YYYYMMDD-HHMMSSX-ZZZ_edited.JPG
#    Foobar.JPG -> YYYYMMDD-HHMMSSX-ZZZ_Foobar.JPG
#
#    X = ImageSeq Number (Basically a way to allow numbering of images when you can take > 1 fps)
#              TODO: This is Very Suboptimal in design as it is only 1 digit, you CAN AND WILL have instances where 0 was after 9, should make this 2 digits
#    YYY = Model Name, like A70 or G3 or 10D so I know which camera took the photo
@traced
@logged
def new_filename(data):
    global counter
    counter = counter + 1
    oldname = data["Custom Filename"].printable
    m = re.search("^(.*)\.(jpg|thm|avi)$", oldname, re.IGNORECASE)
    if not m:
        print("ERROR: Unhandled filetype for {0}...".format(oldname), file=sys.stderr)
        raise UserWarning("Unhandled filetype")
        return oldname
    suffix = m.group(2)
    base = m.group(1)

    # Strip out the common naming convention for cameras
    base = re.sub(r"^(?i)(img|dcp|crw|mvi|dscf|pict|hpim)_?(\d+)_?", "", base)

    # Strip out the base handling if the file has already been renamed
    if re.search("^\d\d\d\d\d\d\d\d-", base):
        if re.search("_.*$", base):
            base = re.sub("^.*_", "", base)
        else:
            base = ""

    # Strip out the base handling if the file is named in IOS dateformat already
    if re.search("^\d\d\d\d-\d\d-\d\d_\d\d-\d\d-\d\d", base):
        base = ""

    # Add back in the base _ prefix
    if len(base) > 0:
        base = "_" + base
        base = re.sub(r" ", "_", base)
        base = re.sub(r"[\[\(\)\]]", "_", base)

    # Build the date & subsec portion of the filename
    try:
        if "EXIF DateTimeOriginal" in data:
            newfilename = data["EXIF DateTimeOriginal"].printable
        elif "EXIF DateTimeDigitized" in data:
            newfilename = data["EXIF DateTimeDigitized"].printable
        elif "Image DateTime" in data:
            newfilename = data["Image DateTime"].printable
        elif "Custom DateTimeOriginal" in data:
            newfilename = data["Custom DateTimeOriginal"].printable
        elif args.use_ctime:
            newfilename = data["Custom stat-ctime"].printable
        else:
            raise KeyError("Missing EXIF DataTimeOriginal")
    except:
        if debug:
            print("ERROR: Missing EXIF DateTimeOriginal for {0}".format(data["Custom Filepath"]), file=sys.stderr)
        raise KeyError("Missing EXIF DataTimeOriginal")
        return oldname
    newfilename = re.sub(r":", "", newfilename)
    newfilename = re.sub(r" ", "-", newfilename)

    # TODO:  If SubSecTime isnt there use 2 digits from Canon-ImageNumber, MakerNote ImageNumber
    # TODO:  Add in test for borked dates.   Dont want to attempt renames if the data is messed up.
    try:
        if "Image Model" in data:
            modelShort = getModelAlias(data["Image Model"].printable.rstrip())
        else:
            modelShort = "UNK"
            # This is a hack for screenshots on IOS
            if "Custom DateTimeOriginal" in data:
                modelShort = "IOS"
    except:
        print('ERROR: File "{0}"\n'.format(data["Custom Filepath"]), file=sys.stderr)
        print(
            'ERROR: Missing ModelAlias for "{0}"\n'.format(data["Image Model"]), file=sys.stderr,
        )
        raise KeyError("Missing Model Alias")

    # Handle situations with FPS>1
    # Will put in a 2 digit psuedo seq number
    if modelShort == "7D":
        newfilename = newfilename + data["EXIF SubSecTime"].printable
    elif modelShort == "10D":
        try:
            num = int(data["MakerNote ImageNumber"].printable) % 100
        except:
            num = counter
        newfilename = newfilename + "{0:02d}".format(num)
    else:
        src_size = os.path.getsize( data["Custom Filepath"].printable) % 100
        newfilename = newfilename + "{0:02d}".format(src_size)

    # Build the model alias portion of name
    newfilename = newfilename + "-" + modelShort

    # Build the modified base portion of the name
    newfilename = newfilename + base

    # Build the suffix portion of name
    newfilename = newfilename + "." + suffix
    return newfilename


#
# Provide a new directory name that matches my PERSONAL PREFERENCE for organizing images
#
# Use DateTimeOriginal to map directory to
#        yyyy/yyyy-mm_Unprocessed
#
# Pass it the full path to the source image and it will return the folder hierarchy to be placed in
#
@traced
@logged
def new_dirname(data):
    # Build the date & subsec portion of the filename

    if "EXIF DateTimeOriginal" in data:
        datetime = data["EXIF DateTimeOriginal"].printable
    elif "EXIF DateTimeDigitized" in data:
        datetime = data["EXIF DateTimeDigitized"].printable
    elif "Image DateTime" in data:
        datetime = data["Image DateTime"].printable
    elif "Custom DateTimeOriginal" in data:
        datetime = data["Custom DateTimeOriginal"].printable
    elif args.use_ctime:
        datetime = data["Custom stat-ctime"].printable
    else:
        raise KeyError("Missing EXIF DataTimeOriginal")

    m = re.search(r"^(\d\d\d\d):(\d\d)", datetime)
    newdirname = m.group(1) + os.sep + m.group(1) + "-" + m.group(2) + "_Unprocessed"
    # TODO:  If DateTimeOriginal isnt there use Stat-mtime
    # TODO:  Add in test for borked dates.   Dont want to attempt renames if the data is messed up.
    #    data['Custom Filepath'] = exifread.IfdTag(fpath, None, 2, None, None, None)
    return newdirname


@traced
@logged
def merge_dicts(*dict_args):
    """
    Given any number of dicts, shallow copy and merge into a new dict,
    precedence goes to key value pairs in latter dicts.
    """
    result = {}
    for dictionary in dict_args:
        result.update(dictionary)
    return result


#
# This is a custom override that add some additional information to EXIF
# Specifically it adds
#     ctime, mtime, atime
#     filename
#     custom fields (derived from comments)
#
@traced
@logged
def process_file(fpath):
    try:
        file = open(fpath, "rb")
    except:
        print("'%s' is unreadable\n" % fpath, file=sys.stderr)
        exit(1)
    # TODO: Fix avi/mov handling here
    fpath_basename = os.path.basename(fpath)
    fpath_dirname = os.path.dirname(fpath)
    if not fpath_dirname:
        fpath_dirname = "."
    fpath = fpath_dirname + os.sep + fpath_basename
    data = exifread.process_file(file, details=True)
    # print("Data = {}".format(data))

    # Populate the exif information with our own custom data
    statinfo = os.stat(fpath)
    data["Custom Filepath"] = exifread.IfdTag(fpath, None, 2, None, None, None)
    data["Custom Filename"] = exifread.IfdTag(fpath_basename, None, 2, None, None, None)
    data["Custom Dirname"] = exifread.IfdTag(fpath_dirname, None, 2, None, None, None)
    data["Custom stat-atime"] = exifread.IfdTag(
        time.strftime("%Y:%m:%d %H:%M:%S", time.localtime(statinfo.st_atime)), None, 2, None, None, None,
    )
    data["Custom stat-ctime"] = exifread.IfdTag(
        time.strftime("%Y:%m:%d %H:%M:%S", time.localtime(statinfo.st_ctime)), None, 2, None, None, None,
    )
    data["Custom stat-mtime"] = exifread.IfdTag(
        time.strftime("%Y:%m:%d %H:%M:%S", time.localtime(statinfo.st_mtime)), None, 2, None, None, None,
    )
    # Strip out the base handling if the file has already been renamed
    base = fpath_basename.split(".")[0]
    if re.search("^\d\d\d\d-\d\d-\d\d_\d\d-\d\d-\d\d", base):
        base = re.sub("_", " ", base)
        base = re.sub("-", ":", base)
        data["Custom DateTimeOriginal"] = exifread.IfdTag(base, None, 2, None, None, None)
    return data


# sub-command functions
@traced
@logged
def cmd_photo_rename(args):
    for filename in args.files[0]:
        if not os.path.isfile(filename):
            print("SKIPPING: {} is not a file".format(filename, file=sys.stderr))
            continue
        try:
            data = process_file(filename)
            newname = new_filename(data)
            newdir = new_dirname(data)
        except SystemExit:
            print("Exiting!", file=sys.stderr)
            exit(1)
        except:
            print(
                "SKIPPING: {} due to errors ({}: {})".format(filename, sys.exc_info()[0], sys.exc_info()[1]),
                file=sys.stderr,
            )
            if debug:
                print("Details {}".format(traceback.format_exc()), file=sys.stderr)
            continue
        newpath = "{target_prefix}/{target_dir}/{target_name}".format(
            target_prefix=args.target_prefix, target_dir=newdir, target_name=newname
        )
        newdir = "{target_prefix}/{target_dir}".format(target_prefix=args.target_prefix, target_dir=newdir)
        if args.verbose:
            print("\n")
            print("Original")
            print("   Filepath:   {0}".format(data["Custom Filepath"]))
            print("    Dirname:   {0}".format(data["Custom Dirname"]))
            print("   Filename:   {0}".format(data["Custom Filename"]))
            print("Renamed")
            print("   Filepath:   {0}".format(newpath))
            print("    Dirname:   {0}".format(newdir))
            print("   Filename:   {0}".format(newname))

        try:
            # if target already exists, check if same size, error unless force
            if os.path.isfile(newpath):
                target_size = os.path.getsize(newpath)
                src_size = os.path.getsize(filename)
                if not args.force:
                    if target_size == src_size:
                        if args.delete:
                            os.remove(filename)
                            raise IOError("Destination exists, with same size. Removing.")
                        raise IOError("Destination exists, with same size")
                    else:
                        raise IOError("Destination exists, with DIFFERENT size.  Would destroy destination.")
            if not args.dryrun:
                if not os.path.isdir(newdir):
                    if debug:
                        print(f"Making target directory {newdir}")
                    os.makedirs(newdir)
                shutil.move(filename, newpath)
            print("{0} -> {1}".format(data["Custom Filepath"], newpath))
        except:
            print(
                "SKIPPING: {} due to errors ({}: {})".format(filename, sys.exc_info()[0], sys.exc_info()[1]),
                file=sys.stderr,
            )
            if debug:
                print("Details {}".format(traceback.format_exc()), file=sys.stderr)
            continue


@traced
@logged
def cmd_photo_unload(args):
    files=[]
    for dir in args.dirs[0]:
        if not os.path.isdir(dir):
            print("SKIPPING: {} is not a directory".format(dir, file=sys.stderr))
            continue
        images = re.compile(".*(JPG|JPEG)$", flags=re.IGNORECASE)
        for path in glob.iglob(f'{dir}/**', recursive=True):
            if os.path.isfile(path) and images.match(path):
                files.append(path)
#    for file in files:
#        print(file)
    args.files=[]
    args.files.append(files)
    cmd_photo_rename(args)
    return


@traced
@logged
def cmd_photo_exif(args):
    err = 0
    for filename in args.files[0]:
        if not os.path.isfile(filename):
            print("'%s' doesn't exist...\n" % filename)
            err += 1
            continue
        print(filename + ":")
        data = process_file(filename)
        if not data:
            print("   No EXIF information found")
            continue

        x = list(data.keys())
        x.sort()
        for i in x:
            if i in ("JPEGThumbnail", "TIFFThumbnail"):
                continue
            try:
                print("   [%s] (%s): %s" % (i, exifread.FIELD_TYPES[data[i].field_type][2], data[i].printable,))
            except:
                print("error", i, '"', data[i], '"')
        print()
    exit(err)


if __name__ == "__main__":
    # create the top-level parser
    parser = argparse.ArgumentParser()
    parser.add_argument("--version", action="version", version="1.0")
    parser.add_argument(
        "-d", "--debug", help="additional debug information", dest="debug", default=0, action="count"
    )
    subparsers = parser.add_subparsers()

    # create the parser for the "exif" command
    parser_exif = subparsers.add_parser("exif")
    parser_exif.add_argument("files", help="files to process", nargs="*", action="append")
    parser_exif.add_argument("-T", "--tagname", help="only show tagname", dest="tagname", action="append")
    parser_exif.set_defaults(func=cmd_photo_exif)

    # create the parser for the "rename" command
    parser_rename = subparsers.add_parser("rename")
    parser_rename.add_argument(
        "-f", "--force", help="force overwrite", dest="force", action="store_true",
    )
    parser_rename.add_argument(
        "-U", "--use-unknown", help="use UNK as camera model", dest="use_unknown", action="store_true",
    )
    parser_rename.add_argument(
        "--use-ctime", help="use fstat-ctime as create date", dest="use_ctime", action="store_true",
    )
    parser_rename.add_argument(
        "-v", "--verbose", help="output verbose information", dest="verbose", action="store_true",
    )
    parser_rename.add_argument(
        "-n", "--dry-run", help="perform a trial run with no changes made", dest="dryrun", action="store_true",
    )
    parser_rename.add_argument(
        "-d", "--delete", help="delete source if target already exists", dest="delete", action="store_true",
    )
    parser_rename.add_argument(
        "-t",
        "--target-prefix",
        help="location where the files will be moved to on rename (default is .)",
        dest="target_prefix",
        default=".",
    )
    parser_rename.add_argument("files", help="files to process", nargs="*", action="append")
    parser_rename.set_defaults(func=cmd_photo_rename)

    # create the parser for the "unload" command
    parser_unload = subparsers.add_parser("unload")
    parser_unload.add_argument(
        "-n", "--dry-run", help="perform a trial run with no changes made", dest="dryrun", action="store_true",
    )  # --dry-run
    parser_unload.add_argument(
        "-f", "--force", help="force overwrite", dest="force", action="store_true",
    )
    parser_unload.add_argument(
        "-U", "--use-unknown", help="use UNK as camera model", dest="use_unknown", action="store_true",
    )
    parser_unload.add_argument(
        "--use-ctime", help="use fstat-ctime as create date", dest="use_ctime", action="store_true",
    )
    parser_unload.add_argument(
        "-d", "--delete", help="delete source if target already exists", dest="delete", action="store_true",
    )
    parser_unload.add_argument(
        "-v", "--verbose", help="output verbose information", dest="verbose", action="store_true",
    )
    parser_unload.add_argument(
        "-t",
        "--target-prefix",
        help="location where the files will be moved to on rename (default is .)",
        dest="target_prefix",
        default=".",
    )
    parser_unload.add_argument("dirs", help="directories to unload recursively", nargs="*", action="append")
    parser_unload.set_defaults(func=cmd_photo_unload)

    # parse the args and call whatever function was selected
    args = parser.parse_args()
    if not debug:
        debug = args.debug>=1

    if args.debug>=2:
        logging.basicConfig(level=TRACE, stream=sys.stderr, format="%(levelname)s:%(filename)s,%(lineno)d:%(name)s.%(funcName)s:%(message)s")
    try:
        func = args.func
    except AttributeError:
        parser.error("too few arguments")
    func(args)
