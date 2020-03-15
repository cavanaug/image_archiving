#   ___                             ____                                                        
#  |_ _|_ __ ___   __ _  __ _  ___ / ___|___  _ __ ___  _ __ ___   ___  _ __    _ __  _ __ ___  
#   | || '_ ` _ \ / _` |/ _` |/ _ \ |   / _ \| '_ ` _ \| '_ ` _ \ / _ \| '_ \  | '_ \| '_ ` _ \ 
#   | || | | | | | (_| | (_| |  __/ |__| (_) | | | | | | | | | | | (_) | | | |_| |_) | | | | | |
#  |___|_| |_| |_|\__,_|\__, |\___|\____\___/|_| |_| |_|_| |_| |_|\___/|_| |_(_) .__/|_| |_| |_|
#                       |___/                                                  |_|              

############################################################################## 
# Public Functions
#    full_image_info
#    new_file_name
# 
#
############################################################################## 
# Private Functions
#    normalize_path
#    addCustomInfo
#    simple_image_info
#
############################################################################## 

use File::stat;
use File::Spec;
use File::Basename;
use Image::Info qw(image_info dim);
use POSIX qw(strftime);


use strict;

#
# Aliases for Renaming
#
my %modelAlias = (
#
#  Current Cameras
#
   "Canon EOS 10D" => "10D",                    # John
   "Canon EOS 20D" => "20D",                    # Peter
   "Canon PowerShot SD500" => "S500",           # Jen
   "Canon PowerShot G3" => "G3",                # Lolo
   "Canon PowerShot SD800 IS" => "S800",        # Lola
   "Canon PowerShot A70" => "A70",              # Grandpa / Jen Old / Lola Old
   "HP PhotoSmart R607 (V01.00)" => "R607",     # Granny 
   "Vivicam 5299" => "VIV",                     # Kaitlyn

#
#  Old Cameras
#
   "FinePix2400Zoom" => "FZ",                   # Johns Old
   "KODAK DX3900 ZOOM DIGITAL CAMERA" => "DX",
   "MX-2700" => "MX",

#
#  Misc/Unknown Cameras
#
   "Canon EOS 30D" => "30D",
   "Canon EOS 40D" => "40D",
   "Canon EOS 50D" => "50D",
   "Canon EOS 60D" => "60D",
   "Canon PowerShot S200" => "S200",
   "Canon PowerShot SD550" => "S550",

   "PENTAX Optio S60" => "OTHER",
   "Unknown" => "UNK",
);

#
# This should really be turned into a sub class of image info
#
my @simpleFields = qw(
   Filename
   Filesize
   ImageSerialNum
   CameraModel
   DateTime
   Resolution
   ExposureTime
   Aperture
   MaxApertureValue
   ExposureBias
   ExposureMode
   MeteringMode
   ISO
   Lens
   FocalLength
   FocalLength35mmEquiv
   Orientation
   Quality
   WhiteBalance
   Saturation
   Sharpness
   Contrast
   Comment
);

#
# Normalize pathname
#
# This is VERY win32 specific
sub normalize_path
{
   my ($file)=@_;
   $file=File::Spec->rel2abs($file);  # On win32 this also appears to lowercase the name (which is good)
   $file=~s(\\)(/)g;
   $file=~s/\/[^\/]*\/\.\.\//\//g;   # LAME.  It should do this for me...
   # TODO: add in the drive letter if it is absent
   return $file;
}

#
# Johns replacement for the generic image_info, it basically DWIW
#
sub full_image_info
{
   my ($file) = @_;
   my $info;
   
   $info=image_info($file);            # Basic image_info
   $info=sanitizeImageInfo($info);     # Clean it up
   $info=addCustomInfo($file,$info);   # Add in Johns specific information

   return $info;
}

sub custom_image_info
{
   my ($file) = @_;
   my $info;
   
   $info=image_info($file);            # Basic image_info
   $info=addCustomInfo($file,$info);   # Add in Johns specific information

   return $info;
}

#
# Take a pointer to an image_info result & sanitize the values
# modify the image_info result in place with santized values
#
# Sanitize the values (ie. convert 35/10 to 3.5)
# Im not sure why this isnt done by default???
sub sanitizeImageInfo
{
  my ($info) = @_;
  
  #
  # Sanitize items
  #
  for my $i (sort(keys(%$info)))
  {
  # Expand items with division like 56/10 which should be 5.6
  #    TODO: Check for div by 0 errors
     if ( $info->{$i} =~ m/^-?\d+\/\d+$/ )
       { $info->{$i} = eval "$info->{$i}"; }
  # Expand Arrays Refs
     if ( ref($info->{$i}) eq "ARRAY" ) 
       { $info->{$i} = '[ ' . join(', ', @{$info->{$i}}) . ' ]'; }
  
  }

  return $info;
}

sub addCustomInfo
{
  my ($file, $info) = @_;

  $info->{'Filename'}=$file;
  #
  # Overload & add in John custom meta-data
  #
  if ( $info->{Comment} =~ m/^:.*:$/ )
    {
      my ($field) = grep(/^:.*:$/, split('\n', $info->{Comment}));
      $field =~ s/^://; $field =~ s/:$//;
      for my $i ( split(':', $field) )
      {
         $info->{'Custom-' . $i}='1';
      }
    }

  my $st=stat($file);
  $info->{'Stat-mtime'}=strftime "%Y:%m:%d %H:%M:%S", (localtime $st->mtime)[0..5];
  $info->{'Stat-ctime'}=strftime "%Y:%m:%d %H:%M:%S", (localtime $st->ctime)[0..5];
  $info->{'Stat-atime'}=strftime "%Y:%m:%d %H:%M:%S", (localtime $st->atime)[0..5];
#  $info->{'Stat-mtime'}=$st->mtime;
#  $info->{'Stat-ctime'}=$st->ctime;
#  $info->{'Stat-atime'}=$st->atime;

  return $info;
}

#
# Take a pointer to an image_info result and return a simple_image_info
#
# This is a subset of information from the main EXIF, but things are named DWIW
#
sub simple_image_info
{
  my ($info) = @_;
  my (%info_simple)=();
  #
  # Compute the simple information
  #
  my %focalPlaneConversion = (
  		"dpi" => 25.4,
  		"dpm" => 25.4,
  		"dpcm" => 10,
  		"dpmm" => 1,
  		"dpµm" => .001 );
  
  #
  # Postprocess & define important parameters
  #   Note: This should be broken into functions that can be overloaded by camera model etc...
  #
  $info_simple{Filename}=$info->{Filename};
  $info_simple{CameraMake}=$info->{Make};
  $info_simple{CameraModel}=$info->{Model};
  $info_simple{Resolution}="$info->{ExifImageWidth} x $info->{ExifImageLength}";
  if ( $info->{FocalPlaneXResolution} ) 
    { $info_simple{CCD_Size}= sprintf("%.2f",$info->{ExifImageWidth} * $focalPlaneConversion{$info->{FocalPlaneResolutionUnit}} / $info->{FocalPlaneXResolution}); }
  else
    { $info_simple{CCD_Size}= "Unknown"; }
  
  $info_simple{Aperture}= $info->{FNumber};
  $info_simple{FocalLength}= $info->{FocalLength};
  
  if ( $info->{FocalLength} && $info->{FocalPlaneXResolution} ) 
    { $info_simple{FocalLength35mmEquiv}= int($info->{FocalLength} * 36 / ($info->{ExifImageWidth} * $focalPlaneConversion{$info->{FocalPlaneResolutionUnit}} / $info->{FocalPlaneXResolution})); }
  else
    { $info_simple{FocalLength35mmEquiv}= "Unknown"; }
  
  $info_simple{ISO}= $info->{ISOSpeedRatings};
  
  if ( $info->{ExposureTime} )
    { $info_simple{ExposureTime}= "1/" . sprintf("%d",1/$info->{ExposureTime}); }
  else
    { $info_simple{ExposureTime}= "Unknown"; }
  $info_simple{ExposureTimeDec}= $info->{ExposureTime};
  $info_simple{MeteringMode}= $info->{"$info_simple{CameraMake}-MeteringMode"} ? 
                              $info->{"$info_simple{CameraMake}-MeteringMode"} : $info_simple{MeteringMode};
  $info_simple{DateTime}= $info->{DateTime};
  $info_simple{Filesize}=int($info->{'Canon-Filesize'}/1024) . " kb";
  $info_simple{Firmware}=$info->{'Canon-FirmwareVersion'};
  $info_simple{OwnerName}=$info->{'Canon-OwnerName'};
  $info_simple{Comment}=$info->{'Comment'};
  $info_simple{ImageSerialNum}=$info->{'Canon-ImageNumber'};
  $info_simple{Quality}=$info->{'Canon-ImageSize'};
  $info_simple{Saturation}=$info->{'Canon-Saturation'};
  $info_simple{WhiteBalance}=$info->{'Canon-WhiteBalance'};
  $info_simple{Sharpness}=$info->{'Canon-Sharpness'};
  $info_simple{Contrast}=$info->{'Canon-Contrast'};
  $info_simple{Orientation}=$info->{Orientation};
  $info_simple{ExposureBias}=$info->{ExposureBiasValue};
  $info_simple{MaxApertureValue}=sprintf("%.1f",sqrt(2)**($info->{MaxApertureValue}));
  if ( $info->{'Canon-ShortFocalLengthOfLensInFocalUnits'} 
       eq $info->{'Canon-LongFocalLengthOfLensInFocalUnits'} )
    { $info_simple{Lens}=$info->{'Canon-ShortFocalLengthOfLensInFocalUnits'}; }
    else 
    { $info_simple{Lens}=$info->{'Canon-ShortFocalLengthOfLensInFocalUnits'} . "-" 
                         . $info->{'Canon-LongFocalLengthOfLensInFocalUnits'}; }
  if ( $info->{'Canon-ExposureMode'} eq 'Easy Shooting' ) 
    { $info_simple{ExposureMode}=$info->{'Canon-EasyShootingMode'}; }
    else { $info_simple{ExposureMode}=$info->{'Canon-ExposureMode'}; }
  
  my @barfoo=keys(%$info); 
  for my $i ( grep(/^(Custom|Stat)-/, @barfoo) )
  {
     $info_simple{$i}=$info->{$i};
  }

  # Filename = NOT STORED IN EXIF
  # Comment = UserComment (Needs some trimming though)
  # AF Mode
  # Flash
  # Orientation (Landscape or portrait) Orientation, top_left = Landscape, left_bot = Portrait
  # MaxApertureValue = fnumber = sqrt(2)^MaxApertureValue   (Maxaperture at a particular focal length)
  
  # Print just the more useful information

  return %info_simple;
}

#
# Provide a new file name that matches my PERSONAL PREFERENCE for image filenames
#
# Pass it the full path to the source image and it will return the basename of the newfilename to be used
#
# Desired behavior is something like these examples:
#    IMG_0429JPG -> YYYYMMDD-HHMMSSX-YYY.JPG
#    IMG_0429_edited.JPG -> YYYYMMDD-HHMMSSX-YYY_edited.JPG
#    Foobar.JPG -> YYYYMMDD-HHMMSSX-YYY_Foobar.JPG
#
#    X = ImageSeq Number (Basically a way to allow numbering of images when you can take > 1 fps)  
#              TODO: This is Very Suboptimal in design as it is only 1 digit, you CAN AND WILL have instances where 0 was after 9, should make this 2 digits
#    YYY = Model Name, like A70 or G3 or 10D so I know which camera took the photo
sub new_file_name
{
my $oldfilename=shift;
my ($trail, $dir, $type)=fileparse($oldfilename, qr{\..*});

#
# Need to do special magic for canon raw files & avi files with associating thm files that have exif data in them
#
# NOTE: The important thing here is that if you want to rename a tree of files you MUST rename the AVI & CRW first, THEN then THM files
if ( $oldfilename =~ m/\.(avi|crw)$/i )
{
  # Special Handling for AVI & RAW Files
  if ( -f "$dir/$trail\.thm" )
  {
     my ($t_base, $t_dir, $t_type) = fileparse(new_file_name("$dir/$trail\.thm"), qr{\..*});
     return $t_base . $type;
  }
}
unless ($oldfilename =~ m/\.(jpg|thm|avi)$/i ) # ESCAPE: We only handle JPG files...
{
  print STDERR "ERROR: Unhandled filetype for $oldfilename...\n";
  return $oldfilename;
}


my %info_simple = ();
my $info = custom_image_info($oldfilename);

my $model;
my $modelfull=$info->{Model};
if ($modelAlias{$modelfull})
{ $model=$modelAlias{$modelfull};   $model =~ s/^.* //g; }
else
{ 
   print STDERR "WARNING: File $oldfilename is listed as Model $modelfull without any alias \n";
   $modelfull="Unknown"; 
   $model=$modelAlias{$modelfull};
}


#
# Create the filename we want to use...  Its of the format YYYYMMDD-HHMMSSX-YYY
#   where X is the last digit of the image number (This is needed on fast cameras that can
#                                                  have greater than 1 fps)
#         Y is the model of camera (ie. 10D, A70, G3, etc)
#
my $newfilename;

if ($info->{DateTimeOriginal})
{ $newfilename=$info->{DateTimeOriginal}; }
elsif ($info->{DateTimeDigitized})
{ $newfilename=$info->{DateTimeDigitized}; }
elsif ($info->{DateTime})
{ $newfilename=$info->{DateTime}; }
else
{ $newfilename=$info->{'Stat-mtime'}; }
$newfilename=~ s/://g;
$newfilename=~ s/ /-/g;
my $imagenum=substr $info->{'Canon-ImageNumber'}, -1, 1;  $imagenum=0 unless $imagenum;
$newfilename.= ($imagenum="" ? 0 : $imagenum);

unless ($newfilename =~ m/^\d\d\d\d\d\d\d\d-/ )  # Skip it completely if the EXIF date is torqued
{
  print STDERR "ERROR: EXIF Date $newfilename unrecognizable for $oldfilename...\n";
  return $oldfilename;
}

# Avoid renaming files that are already in the proper format...
#if ( $oldfilename =~ m/^$newfilename(.*)/ )
if ( $newfilename eq substr($oldfilename, 0, length($newfilename) ) )
#{ print "MATCH: Skipping\n"; next; }
{ return $oldfilename; }

#
# Lets examine if the original is in a format other than IMG_####.JPG
#
# Desired behavior is something like these examples:
#    IMG_0429_edited.JPG -> YYYYMMDD-HHMMSSX-YYY_edited.JPG
#    Foobar.JPG -> YYYYMMDD-HHMMSSX-YYY_Foobar.JPG
#

next if ( $trail =~ m/^$newfilename/ ); # ESCAPE: If it looks the same lets skip it...

$trail=~ s/\....$//;   # This is probably a little risky to do without checking file extension
if ( $trail =~ m/^IMG_/i )  # Keep the filds like _edited on the end
{  $trail=~ s/^[Ii][Mm][Gg]_(\d+)//g;  }
elsif ( $trail =~ m/^DSCF/i )  # Keep the filds like _edited on the end
{  $trail=~ s/^[Dd][Ss][Cc][Ff](\d+)//g;  }
elsif ( $trail =~ m/^PICT/i )  # Keep the filds like _edited on the end
{  $trail=~ s/^[Pp][Ii][Cc][Tt](\d+)//g;  }
elsif ( $trail =~ m/^DCP_/i )  # Keep the filds like _edited on the end
{  $trail=~ s/^[Dd][Cc][Pp]_(\d+)//g;  }
elsif ( $trail =~ m/^HPIM/i )  # Keep the filds like _edited on the end
{  $trail=~ s/^[Hh][Pp][Ii][Mm](\d+)//g;  }
elsif ( $trail =~ m/^CRW_/i )  # Keep the filds like _edited on the end
{  $trail=~ s/^[Cc][Rr][Ww]_(\d+)//g;  }
elsif ( $trail =~ m/^MVI_/i )  # Keep the filds like _edited on the end
{  $trail=~ s/^[Mm][Vv][Ii]_(\d+)//g;  }
elsif ( $trail =~ m/^VID/i )  # Keep the filds like _edited on the end
{  $trail=~ s/^[Vv][Ii][Dd](\d+)//g;  }
elsif ( $trail =~ /^\d\d\d\d\d\d\d\d-/ )  # Rename it completely if the EXIF got reset (Will lose end fields)
{ 
  if ( $trail =~ /_.*$/ )
   { $trail =~ s/^.*_//g; }
  else
   { $trail = ""; }
}
else  # Allow for Foobar like names
{  ; }
$trail="" if $trail eq "_";
$trail= "_" . $trail if $trail; 
$trail =~ s/^_+/_/; 
#$newfilename= dirname($oldfilename) . "/" . $newfilename . "-" . $model . $trail . $type;  # TODO: Maybe refactor this later...
$newfilename= $newfilename . "-" . $model . $trail . $type;  # TODO: Maybe refactor this later...

return $newfilename
}
