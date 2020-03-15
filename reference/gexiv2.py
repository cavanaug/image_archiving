#!/usr/bin/env python3
import gi
gi.require_version('GExiv2', '0.10')

from gi.repository import GExiv2 

file='IMG_7695.JPG'

exif = GExiv2.Metadata(file)

exif['Filepath']=file
exif['Filename']=file

for i in exif:
    print("{} = {}".format(i, exif[i]))

