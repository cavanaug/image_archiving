#!/usr/bin/env python3
# from __future__ import print_function
import argparse
import sys
import os
import os.path
import time
import re
import exifread
import shutil
import subprocess
import glob
import json
import pprint

import traceback
import logging

from pathlib import Path

from autologging import logged, TRACE, traced


debug = False

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


#
# Put all the logic for creating the short model name in one place
#
def getModelAlias(data):
    try:
        model = data["EXIF:Model"]
    except:
        raise KeyError("Missing Model Information")
    if args.use_unknown:
        modelShort = "UNK"
        if model in modelAlias:
            modelShort = modelAlias[model]
    else:
        modelShort = modelAlias[model]
    return modelShort


def getCreateDate(data):
    if "EXIF:DateTimeOriginal" in data:
        datetime = data["EXIF:DateTimeOriginal"]
    elif "EXIF:DateTimeDigitized" in data:
        datetime = data["EXIF:DateTimeDigitized"]
    elif "EXIF:CreateDate" in data:
        datetime = data["EXIF:CreateDate"]
    elif "Custom:DateTimeOriginal" in data:  # Based on filename
        datetime = data["Custom:FileNameDate"]
    elif args.use_ctime:
        datetime = data["Custom:stat-ctime"]
    else:
        raise KeyError("ERROR: Cant determine Creation Date for file")
    return datetime


def getSeqNumXX(data):
    # Handle situations with FPS>1
    # Will put in a 2 digit psuedo seq number

    if "Composite:FileNumber" in data:
        seqnum = int(data["Composite:FileNumber"].split("-")[1])
    else:
        for item in ["EXIF:SubSecTime", "EXIF:SubSecTimeDigitized", "EXIF:SubSecTimeDigitized", "Custom:FileSize"]:
            if item in data:
                seqnum = data[item]
                break
    return "{0:02d}".format(seqnum % 100)


#
# Provide a new file name that matches my PERSONAL PREFERENCE for image filenames
#
# Pass it the full path to the source image and it will return the basename of the newfilename to be used
#
# Desired behavior is something like these examples:
#    IMG_0429.JPG -> YYYYMMDD-HHMMSSXX-ZZZ.JPG
#    IMG_0429_edited.JPG -> YYYYMMDD-HHMMSSX-ZZZ_edited.JPG
#    Foobar.JPG -> YYYYMMDD-HHMMSSXX-ZZZ_Foobar.JPG
#
#    XX = ImageSeq Number (Basically a way to allow numbering of images when you can take > 1 fps)
#             SubSecTime
#             ImageNumber modulo 100
#             Filesize modulo 100
#         TODO: This isnt perfect, you CAN AND WILL have instances where 00 was after 99
#    ZZZ = Model Name Alias, like A70 or G3 or 10D so I know which camera took the photo immediately
def new_filename(data):
    oldname = data["File:FileName"]
    m = re.search("^(.*)\.(jpg|thm|avi|mov|mts)$", oldname, re.IGNORECASE)
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

    # Strip out the base handling if the file is named in a dateformat already
    if re.search("^\d\d\d\d-\d\d-\d\d_\d\d-\d\d-\d\d", base):
        base = ""

    # Add back in the base _ prefix
    if len(base) > 0:
        base = "_" + base
        base = re.sub(r" ", "_", base)
        base = re.sub(r"[\[\(\)\]]", "_", base)

    # Build the date & subsec portion of the filename
    try:
        newfilename = getCreateDate(data)
    except:
        if debug:
            print("ERROR: Missing EXIF DateTimeOriginal for {0}".format(data["SourceFile"]), file=sys.stderr)
        raise KeyError("ERROR: Cant determine Creation Date for file")
    newfilename = re.sub(r":", "", newfilename)
    newfilename = re.sub(r" ", "-", newfilename)

    # Handle situations with FPS>1
    # Will put in a 2 digit psuedo seq number
    seqnumXX = getSeqNumXX(data)
    newfilename = newfilename + seqnumXX

    try:
        modelShort = getModelAlias(data)
    except:
        print('ERROR: File "{0}"\n'.format(data["SourceFile"]), file=sys.stderr)
        print(
            'ERROR: Cant determine ModelAlias for "{0}"\n'.format(data["EXIF:Model"]), file=sys.stderr,
        )
        raise KeyError("Missing Model or Model Alias")

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
def new_dirname(data):
    datetime = getCreateDate(data)
    m = re.search(r"^(\d\d\d\d):(\d\d)", datetime)
    newdirname = m.group(1) + os.sep + m.group(1) + "-" + m.group(2) + "_Unprocessed"
    return newdirname


#
# This is a custom override that add some additional information to EXIF
# Specifically it adds
#     ctime, mtime, atime
#     filename
#     custom fields (derived from comments)
#
def process_file(fpath):
    try:
        file = open(fpath, "rb")
    except:
        print("'%s' is unreadable\n" % fpath, file=sys.stderr)
        exit(1)
    fpath_basename = os.path.basename(fpath)
    fpath_dirname = os.path.dirname(fpath)
    if not fpath_dirname:
        fpath_dirname = "."
    fpath = fpath_dirname + os.sep + fpath_basename
    data = json.loads(subprocess.check_output(args=["exiftool", "-G", "-j", fpath]))[0]

    # Populate the exif information with our own custom data
    statinfo = os.stat(fpath)
    data["Custom:stat-atime"] = time.strftime("%Y:%m:%d %H:%M:%S", time.localtime(statinfo.st_atime))
    data["Custom:stat-ctime"] = time.strftime("%Y:%m:%d %H:%M:%S", time.localtime(statinfo.st_ctime))
    data["Custom:stat-mtime"] = time.strftime("%Y:%m:%d %H:%M:%S", time.localtime(statinfo.st_mtime))
    data["Custom:FileSize"] = os.path.getsize(fpath)

    # Strip out the base handling if the file has already been renamed
    base = fpath_basename.split(".")[0]
    if re.search("^\d\d\d\d-\d\d-\d\d_\d\d-\d\d-\d\d", base):
        base = re.sub("_", " ", base)
        base = re.sub("-", ":", base)
        data["Custom:FileNameDate"] = base
    return data


def process_file_old(fpath):
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
    data["Custom:FilePath"] = exifread.IfdTag(fpath, None, 2, None, None, None)
    data["Custom:FileName"] = exifread.IfdTag(fpath_basename, None, 2, None, None, None)
    data["Custom:DirName"] = exifread.IfdTag(fpath_dirname, None, 2, None, None, None)
    data["Custom:stat-atime"] = exifread.IfdTag(time.strftime("%Y:%m:%d %H:%M:%S", time.localtime(statinfo.st_atime)), None, 2, None, None, None,)
    data["Custom:stat-ctime"] = exifread.IfdTag(time.strftime("%Y:%m:%d %H:%M:%S", time.localtime(statinfo.st_ctime)), None, 2, None, None, None,)
    data["Custom:stat-mtime"] = exifread.IfdTag(time.strftime("%Y:%m:%d %H:%M:%S", time.localtime(statinfo.st_mtime)), None, 2, None, None, None,)
    # Strip out the base handling if the file has already been renamed
    base = fpath_basename.split(".")[0]
    if re.search("^\d\d\d\d-\d\d-\d\d_\d\d-\d\d-\d\d", base):
        base = re.sub("_", " ", base)
        base = re.sub("-", ":", base)
        data["Custom DateTimeOriginal"] = exifread.IfdTag(base, None, 2, None, None, None)
    return data


# sub-command functions
def cmd_photo_rename(args):
    for filename in args.files[0]:
        if not os.path.isfile(filename):
            print("SKIPPING: {} is not a file".format(filename, file=sys.stderr))
            continue
        try:
            data = process_file(filename)
#            pp.pprint(data)
            newname = new_filename(data)
            newdir = new_dirname(data)
        except SystemExit:
            print("Exiting!", file=sys.stderr)
            exit(1)
        except:
            print(
                "SKIPPING: {} due to errors ({}: {})".format(filename, sys.exc_info()[0], sys.exc_info()[1]), file=sys.stderr,
            )
            if debug:
                print("Details {}".format(traceback.format_exc()), file=sys.stderr)
            continue
        newpath = "{target_prefix}/{target_dir}/{target_name}".format(target_prefix=args.target_prefix, target_dir=newdir, target_name=newname)
        newdir = "{target_prefix}/{target_dir}".format(target_prefix=args.target_prefix, target_dir=newdir)
        if args.verbose:
            print("\n")
            print("Original")
            print("   Filepath:   {0}".format(data["SourceFile"]))
            print("    Dirname:   {0}".format(data["File:Directory"]))
            print("   Filename:   {0}".format(data["File:FileName"]))
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
            print("{0} -> {1}".format(data["SourceFile"], newpath))
        except:
            print(
                "SKIPPING: {} due to errors ({}: {})".format(filename, sys.exc_info()[0], sys.exc_info()[1]), file=sys.stderr,
            )
            if debug:
                print("Details {}".format(traceback.format_exc()), file=sys.stderr)
            continue


def cmd_photo_unload(args):
    files = []
    for dir in args.dirs[0]:
        if not os.path.isdir(dir):
            print("SKIPPING: {} is not a directory".format(dir, file=sys.stderr))
            continue
        images = re.compile(".*(JPG|JPEG)$", flags=re.IGNORECASE)
        for path in glob.iglob(f"{dir}/**", recursive=True):
            if os.path.isfile(path) and images.match(path):
                files.append(path)
    #    for file in files:
    #        print(file)
    args.files = []
    args.files.append(files)
    cmd_photo_rename(args)
    return

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
                print("   [%s] (%s): %s" % (i, type(data[i]).__name__.upper(), data[i]))
            except:
                print("error", i, '"', data[i], '"')
        print()
    exit(err)


def cmd_photo_exif2(args):
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
    # Create pretty printer
    pp = pprint.PrettyPrinter(indent=4)

    # create the top-level parser
    parser = argparse.ArgumentParser()
    parser.add_argument("--version", action="version", version="1.0")
    parser.add_argument("-d", "--debug", help="additional debug information", dest="debug", default=0, action="count")
    subparsers = parser.add_subparsers()

    # create the parser for the "exif" command
    parser_exif = subparsers.add_parser("exif", help="show exif data using exiftool (default)")
    parser_exif.add_argument("files", help="files to process", nargs="*", action="append")
    parser_exif.add_argument("-T", "--tagname", help="only show tagname", dest="tagname", action="append")
    parser_exif.set_defaults(func=cmd_photo_exif)

    parser_exif2 = subparsers.add_parser("exif2", help="show exif data using python exifread for comparison")
    parser_exif2.add_argument("files", help="files to process", nargs="*", action="append")
    parser_exif2.add_argument("-T", "--tagname", help="only show tagname", dest="tagname", action="append")
    parser_exif2.set_defaults(func=cmd_photo_exif2)

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
        "-t", "--target-prefix", help="location where the files will be moved to on rename (default is .)", dest="target_prefix", default=".",
    )
    parser_rename.add_argument("files", help="files to process", nargs="*", action="append")
    parser_rename.set_defaults(func=cmd_photo_rename)

    # create the parser for the "unload_photos" command
    parser_unload_photos = subparsers.add_parser("unload_photos", help="recursively unload (find, copy/rename, delete) photos (jpg, jpeg)")
    parser_unload_photos.add_argument("-n", "--dry-run", help="perform a trial run with no changes made", dest="dryrun", action="store_true")
    parser_unload_photos.add_argument(
        "-f", "--force", help="force overwrite", dest="force", action="store_true",
    )
    parser_unload_photos.add_argument(
        "-U", "--use-unknown", help="use UNK as camera model", dest="use_unknown", action="store_true",
    )
    parser_unload_photos.add_argument(
        "--use-ctime", help="use fstat-ctime as create date", dest="use_ctime", action="store_true",
    )
    parser_unload_photos.add_argument(
        "-d", "--delete", help="delete source if target already exists", dest="delete", action="store_true",
    )
    parser_unload_photos.add_argument(
        "-v", "--verbose", help="output verbose information", dest="verbose", action="store_true",
    )
    parser_unload_photos.add_argument(
        "-t", "--target-prefix", help="location where the files will be moved to on rename (default is .)", dest="target_prefix", default=".",
    )
    parser_unload_photos.add_argument("dirs", help="directories to unload recursively", nargs="*", action="append")
    parser_unload_photos.set_defaults(func=cmd_photo_unload)

    # create the parser for the "unload_videos" command
    parser_unload_videos = subparsers.add_parser("unload_videos", help="recursively unload (find, copy/rename, delete) videos (avi, thm, mts, mov)")
    parser_unload_videos.add_argument(
        "-n", "--dry-run", help="perform a trial run with no changes made", dest="dryrun", action="store_true",
    )  # --dry-run
    parser_unload_videos.add_argument(
        "-f", "--force", help="force overwrite", dest="force", action="store_true",
    )
    parser_unload_videos.add_argument(
        "-U", "--use-unknown", help="use UNK as camera model", dest="use_unknown", action="store_true",
    )
    parser_unload_videos.add_argument(
        "--use-ctime", help="use fstat-ctime as create date", dest="use_ctime", action="store_true",
    )
    parser_unload_videos.add_argument(
        "-d", "--delete", help="delete source if target already exists", dest="delete", action="store_true",
    )
    parser_unload_videos.add_argument(
        "-v", "--verbose", help="output verbose information", dest="verbose", action="store_true",
    )
    parser_unload_videos.add_argument(
        "-t", "--target-prefix", help="location where the files will be moved to on rename (default is .)", dest="target_prefix", default=".",
    )
    parser_unload_videos.add_argument("dirs", help="directories to unload recursively", nargs="*", action="append")
    parser_unload_videos.set_defaults(func=cmd_photo_unload)

    # parse the args and call whatever function was selected
    args = parser.parse_args()
    if not debug:
        debug = args.debug >= 1

    try:
        func = args.func
    except AttributeError:
        parser.error("too few arguments")
    func(args)
