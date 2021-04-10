import os
import shutil
from datetime import datetime
from collections import defaultdict
import exifread
import piexif
import hachoir.parser
import hachoir.metadata


class FileInfo:
    def __init__(self, filepath):
        self.filepath = filepath
        self.ext = os.path.splitext(filepath)[1][1:].lower()

        if self.is_pic_or_video():
            print("*" * 20)
            print("Reading", self.filepath)
            self.size = os.path.getsize(self.filepath)
            self.timestamp = self.get_timestamp()
            print("*" * 20)

    def is_video_file(self):
        return self.ext in ["3gp", "avi", "mp4", "mpg", "mts", "mov"]

    def is_pic_file(self):
        return self.is_jpg_file() or self.ext in ["png"]

    def is_jpg_file(self):
        return self.ext in ["jpg", "jpeg"]

    def is_pic_or_video(self):
        return self.is_pic_file() or self.is_video_file()

    def get_timestamp(self):
        modified_time = datetime.fromtimestamp(os.path.getmtime(self.filepath))
        metadata_time = None
        invalid_time = datetime.strptime("1980-01-01", "%Y-%m-%d")

        if self.is_jpg_file():
            try:
                with open(self.filepath, "rb") as f:
                    tags = exifread.process_file(f, details=False, stop_tag="DateTimeOriginal")
                    dt_str = str(tags["EXIF DateTimeOriginal"])

                metadata_time = datetime.strptime(dt_str, "%Y:%m:%d %H:%M:%S")
            except Exception as e:
                print("ERROR: %s" % e)

        elif self.is_video_file() or self.is_pic_file():
            try:  # this try for when the createParser below return None and hence "with" clause fails
                with hachoir.parser.createParser(self.filepath) as parser:
                    metadata = hachoir.metadata.extractMetadata(parser)
                    try:
                        metadata_time = metadata.get("creation_date", default=None)
                    except Exception as e:
                        print("ERROR: Could not fine creation_date from following metadata:")
                        print(metadata)
                        print("Original error:\n%s" % e)
            except Exception as e:
                print("ERROR: \n%s" % e)

        print("metadata time = %s" % metadata_time)
        print("file modified time = %s" % modified_time)

        # date of metadata time and modified time are same then use modified time as metadata time is always UTC.
        if metadata_time and metadata_time.date() != modified_time.date() and invalid_time < metadata_time < modified_time:
            dt = metadata_time
            print("using metadata time")
        else:
            dt = modified_time
            print("using file modified time")

        dt = dt.replace(microsecond=0)  # precision till seconds only.
        return dt


class PicsOrganizer:
    def __init__(self, in_dir, out_dir):
        self.in_dir = in_dir
        self.out_dir = out_dir

    def scan_input_dir(self):
        print("Scanning input dir ", self.in_dir)
        src_dest_tuple_list = []
        dest_set = set()
        for dir_name, sub_dirs_list, files_list in os.walk(self.in_dir):
            sorted_files_list = sorted(files_list)
            for src_file_path in sorted_files_list:
                src_file_path = os.path.join(dir_name, src_file_path)
                info = FileInfo(src_file_path)
                if info.is_pic_or_video():
                    # WARNING: A change here also demands change in parsing below (parts = dest.split("-"))
                    dest_file_name = info.timestamp.strftime("%Y-%m-%d_%H%M%S")
                    org_dest_file = dest_file_name

                    i = 0
                    while dest_file_name in dest_set:
                        i += 1
                        suffix = "D%03d" % i
                        dest_file_name = "%s_%s" % (org_dest_file, suffix)

                    if i > 0:
                        print("Duplicate time found '%s' for '%s'" % (org_dest_file, src_file_path))

                    dest_set.add(dest_file_name)
                    date_dir = dest_file_name.split("-")[0]  # folders by years
                    dest_file_path = os.path.join(self.out_dir, date_dir, "%s.%s" % (dest_file_name, info.ext))
                    src_dest_tuple_list.append((src_file_path, dest_file_path))

        return src_dest_tuple_list

    @staticmethod
    def create_dest_dirs(src_dest_tuple_list):
        print("Creating destination dirs...")
        dirs_to_create = set()
        for _, dest in src_dest_tuple_list:
            dirs_to_create.add(os.path.dirname(dest))

        for d in dirs_to_create:
            os.makedirs(d)

    @staticmethod
    def move_files(src_dest_tuple_list):
        print("Moving files...")
        for src, dest in src_dest_tuple_list:
            print(src, "->", dest)
            if os.path.exists(dest):
                raise RuntimeError("Dest file %s already exists" % dest)
            shutil.move(src, dest)

    def run(self):
        files = os.listdir(self.out_dir)
        if files:
            raise RuntimeError("out_dir %s is not empty" % self.out_dir)

        src_dest_tuple_list = self.scan_input_dir()
        self.create_dest_dirs(src_dest_tuple_list)
        self.move_files(src_dest_tuple_list)
        remove_empty_dirs(self.in_dir)


def remove_empty_dirs(dir_path):
    print("Removing empty dirs in %s" % dir_path)
    # walking the tree bottom - up is essential, rmdir() doesn’t allow
    # deleting a non empty directory
    # assuming there are no symbolic links.
    for root, dirs, files in os.walk(dir_path, topdown=False):
        for name in dirs:
            d = os.path.join(root, name)
            if not os.listdir(d):
                os.rmdir(d)


def get_date_folder_month(month):
    if month in [1, 2, 3, 4]:
        return "A"
    if month in [5 ,6 ,7, 8]:
        return "B"
    if month in [9, 10, 11, 12]:
        return "C"

    raise RuntimeError("getDateFolderMonth error for month %d" % month)


def move_files_to_dir(files, dest_dir):
    print("Moving files to dir...")
    for src in files:
        dest = os.path.join(dest_dir, os.path.basename(src))
        print("move", src, "->", dest)
        if os.path.exists(dest):
            raise RuntimeError("Dest file %s already exists" % dest)
        shutil.move(src, dest)


def copy_files_to_dir(files, destDir):
    print("Copy files to dir...")
    for src in files:
        dest = os.path.join(destDir, os.path.basename(src))
        print("copy", src, "->", dest)
        if os.path.exists(dest):
            raise RuntimeError("Dest file %s already exists" % dest)
        shutil.copy(src, dest)


def remove_duplicates():
    in_dir = os.path.normpath(IN_DIR)
    out_dir = os.path.join(in_dir, "dupes")

    files = os.listdir(out_dir)
    if files:
        raise RuntimeError("outdir %s is not empty" % out_dir)

    org_to_dup_files_list_map = defaultdict(set)
    dup = 0
    for dirName, subDirsList, filesList in os.walk(in_dir):
        sorted_files_list = sorted(filesList)
        for file in sorted_files_list:
            if "D" in file:
                dup += 1
                parts = file.split("_")
                org_file = os.path.join(dirName, "%s_%s.%s" % (parts[0], parts[1], parts[2].split(".")[-1]))
                #print file
                if os.path.exists(org_file):
                    org_to_dup_files_list_map[org_file].add(os.path.join(dirName, file))
                else:
                    raise RuntimeError("org file not found: %s" % org_file)
                    #print os.path.join(dirName, file)
                    #moveFiles([(os.path.join(dirName, file), orgFile)])

    print("Total dupes =", dup)
    copy_set = set()
    move_set = set()
    for org_file, dupFiles in org_to_dup_files_list_map.iteritems():
        o_f_size, o_f_time = get_file_modified_time_size(org_file)
        for file in dupFiles:
            f_size, f_time = get_file_modified_time_size(file)
            if o_f_size == f_size and o_f_time == f_time:
                copy_set.add(org_file)
                move_set.add(file)

    copy_files_to_dir(copy_set, out_dir)
    move_files_to_dir(move_set, out_dir)


def print_tags(file, tag_name_like=None):
    exif_dict = piexif.load(file)
    for ifd in ("0th", "Exif", "GPS", "1st"):
        for tag in exif_dict[ifd]:
            name = piexif.TAGS[ifd][tag]["name"]
            if tag_name_like and tag_name_like.lower() in name.lower():
                print(name, exif_dict[ifd][tag])


def set_jpeg_time_from_0th_tag(file):
    exif_dict = piexif.load(file)
    zeroth_time = exif_dict["0th"][piexif.ImageIFD.DateTime]
    exif_dict["Exif"][piexif.ExifIFD.DateTimeOriginal] = zeroth_time
    exif_dict["Exif"][piexif.ExifIFD.DateTimeDigitized] = zeroth_time

    exif_bytes = piexif.dump(exif_dict)
    piexif.insert(exif_bytes, file)


def set_jpeg_time_from_file_mod_time(file):
    mtime = os.path.getmtime(file)
    atime = os.path.getatime(file)
    dt = datetime.fromtimestamp(mtime)

    exif_dict = piexif.load(file)
    str_time = dt.strftime("%Y:%m:%d %H:%M:%S")
    exif_dict["Exif"][piexif.ExifIFD.DateTimeOriginal] = str_time
    exif_dict["Exif"][piexif.ExifIFD.DateTimeDigitized] = str_time

    exif_bytes = piexif.dump(exif_dict)
    piexif.insert(exif_bytes, file)

    os.utime(file, (atime, mtime))


def set_file_mod_time_from_jpeg_time(file):
    exif_dict = piexif.load(file)
    dt = datetime.strptime(exif_dict["Exif"][piexif.ExifIFD.DateTimeOriginal], "%Y:%m:%d %H:%M:%S")
    timestamp = (dt - datetime(1970, 1, 1)).total_seconds()
    os.utime(file, (timestamp, timestamp))


def main():
    IN_DIR = "D:\_00src"
    OUT_DIR = "D:\_00dest"
    IN_DIR = "D:/pics-and-vidoes-src"
    OUT_DIR = "D:/pics-and-vidoes-dest"
    PicsOrganizer(IN_DIR, OUT_DIR).run()


if __name__ == "__main__":
    #test()
    main()
