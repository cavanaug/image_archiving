#!/opt/perl/bin/perl
#
# unloader.pl
#
# Automatically unload image files from a removable media and place in DigitalPhotos Archive
#
# - Copy to <opt_p>/<year>/<year>-<month>_Unprocessed
#   using the date stamp on the file itself on the media (Maybe later use EXIF??)
#   if raw image then put crw & corresponding thm into a subfolder named RAW  
# - Rename files copied using renamer.pl script
# - TBD??  Remove images from media (format or delete???)
#
# Options
#   -p = opt_p [Default E:\DigitalPhotos]
#   -r = rename files [Default off]
#   -d = delete files on media [Default off]
#   -o = orient files (ie. auto rotate if possible) [Default off]
#   -e = use Exif date instead of filesystem date
#   -v = verbose output
#   -j = jpeg extraction from raw images [Default off]
#   <paths> to process
#
#
##################################################################################################
#
# TODO: 
#    - Move to integrated rename on copy utilizing the new_file_name function in ImageCommon
#    - Support CRW & AVI files with renaming
#    - Support auto extraction of JPG's from CRW's (as another phase, probably -j) 
#        - Also need to copy exif from thm file to this jpg
#        - This phase needs to occur before orientation correction so the extracted jpgs can be autorotated
#    - Implement -e functionality for Exif date usage
#    - Support destination automation via serial number (That way I can unload cards from other people to a temporary area instead of populating my main area)
#    - Make a GUI for unloader
#      - Checkbox for delete (-d)
#      - Checkbox for orientation correction (-o)
#      - Checkbox for rename (-r)
#      - Checkbox for jpeg extraction from raw files (-j)
#      - Dropdown,with edit, for Destination Root (-p)
#
#
##################################################################################################
my $debug=0;

use File::Find::Rule;
use File::Basename;
use Image::Info qw(image_info dim);
use Data::Dumper;
use Getopt::Std;
use File::Copy;
use File::stat;
use Date::Calc qw(Time_to_Date);
use FindBin;
use lib "$FindBin::Bin";
use lib "$FindBin::Bin/../DatabaseExif";
use lib "$FindBin::Bin/../../DatabaseExif";

#use lib 'C:/users/cavanaug/src_personal/ImageUtils/DatabaseExif';
require "ImageCommon.pm";

#use strict;
my $perl='C:/perl/bin/perl.exe';
my $ksh='C:/gnuwin32/bin/sh.exe';
my $renamer="$FindBin::Bin/../renamer/renamer.pl -b ";
my $orienter="$FindBin::Bin/../rotator/exifautotran.ksh ";
my $extractor="$FindBin::Bin/../exiftool/exiftool.pl -b -JpgFromRaw -o _raw.JPG ";
my $exifcopy='C:/users/cavanaug/bin/jhead.exe -te ';
my $suffix='_Unprocessed';

getopts("p:drevoj");
$opt_p='C:/DigitalPhotos/JohnCavanaugh' unless $opt_p;

#
# TODO: Change logic for application
#       Find all files in one swoop, then segment into thm/jpg/crw/avi ordering
#       Support renaming during copy (allow duplicate filenames on source in different directories)
#       Refactor new filename generation into a function
#            Keep hash of old->new by basename without extension, use this mapping for crw & avi
#       Log message for copy IMG
#
#

for $dir (@ARGV)
{
  my @copiedFiles;
  print "\nFinding Media Files on Source Media ($dir)\n";
  my @jpgfiles= File::Find::Rule->file()
                          ->name( qr/\.(jpg|crw|avi)$/i  )
                          ->in( $dir );
  print "   JPG/CRW/AVI - " . ($#jpgfiles + 1) . " files found\n" if ($opt_v and $#jpgfiles gt -1);
  my @thmfiles= File::Find::Rule->file()
                          ->name( qr/\.(thm)$/i  )
                          ->in( $dir );
  print "   THM - " . ($#thmfiles + 1) . " files found\n" if ($opt_v and $#thmfiles gt -1);
  
  @files=(@thmfiles, @jpgfiles);
  if ($opt_r)
        { print "\nRenaming & Copying Files from Source Media to Destination ($opt_p)\n"; }
   else { print "\nCopying Files from Source Media to Destination ($opt_p)\n"; }
   
  for $file (@files)
  {
     my $st=stat($file);
     my ($year, $month, $day, $nicedate, $destname);

     ($year, $month, $day)=Time_to_Date( $st->mtime );
     $nicedate=sprintf "%04d-%02d", ${year},${month};
     if ($opt_e)
     {
        ; #EXIF DATE ROUTINE
        # Need error handling if exif is bogus...  Fall back to default filesystem date
     }

     mkdir "${opt_p}/${year}" unless (-d "${opt_p}/${year}");
     mkdir "${opt_p}/${year}/${nicedate}${suffix}" unless (-d "${opt_p}/${year}/${nicedate}${suffix}");

     if ($opt_r) { $destname="${opt_p}/${year}/${nicedate}${suffix}/" . new_file_name($file); }
            else { $destname="${opt_p}/${year}/${nicedate}${suffix}/" . basename($file); }
             
     unless ( copy($file,${destname}) )
     { 
        print "\nERROR:  Problems copying $file";
        if ( $opt_d )
        {
           print "\nERROR:  Disabling deletion from source";
           $opt_d=0;
        }
     }
     print "   " . basename($file) . " -> ${destname}\n" if $opt_v;
     push(@copiedFiles,$destname);
  }
  
  if ($opt_j)
  {
    my $cmd;
    print "\nRaw File Handling (JPG Extraction etc) at Destination ($opt_p/...)\n";
    @rawFiles=grep(/.crw$/i, @copiedFiles);
   
    for $i ( @rawFiles )
    {
      $i_thm=$i;  $i_thm =~ s/\.(crw)$/.THM/i;
      $i_jpg=$i;  $i_jpg =~ s/\.(crw)$/_raw.JPG/i;
 
      $i_dir=dirname($i);
      mkdir("$i_dir/RAW") unless -d "$i_dir/RAW";
    
      print "   $i\n";
      $cmd="$perl $extractor $i";  $cmd.=" > nul" unless $debug;
      print "system($cmd)\n" if $debug;  system($cmd);
      push(@copiedFiles, $i_jpg);
      
      if (-f $i_thm )
      { 
        $cmd="$exifcopy $i_thm $i_jpg";  $cmd.=" > nul" unless $debug;     
        print "system($cmd)\n" if $debug;  system($cmd);
      }
      rename($i_thm, "$i_dir/RAW/" . basename($i_thm));
      rename($i, "$i_dir/RAW/" . basename($i));
    }
    print "\n";
  }
 
  
  if ($opt_o)
  {
    my $cmd;
    print "\nOrientation Correction at Destination ($opt_p/...)\n";
    @copiedFiles=grep(/.[Jj][Pp][Gg]$/, @copiedFiles);
    $cmd="$ksh $orienter -q " . join(' ', @copiedFiles);
    $cmd.=" > nul" unless $opt_v;
    print "system($cmd)\n" if $debug;
    system($cmd);
  }


  if ($opt_d)
  {
    print "\nDeleting Files from Source Media ($dir/...)\n";
    for $file (@files)
    {
      print "   $file\n";
      unlink($file);  # Remove
    }
  }
}

