import os
import shutil
from datetime import datetime
from collections import defaultdict
import exifread
import piexif


def is_video_ext(ext):
    return ext in ["3gp", "avi", "mp4", "mpg", "mts"]


def is_pic_ext(ext):
    return ext in ["jpg", "jpeg", "png"]


def get_ext_lower(file):
    return os.path.splitext(file)[1][1:].lower()


def get_file_modified_time(file):
    return datetime.fromtimestamp(os.path.getmtime(file))


def get_file_modified_time_size(file):
    return os.path.getsize(file), get_file_modified_time(file)


def get_jpg_date_time(file):
    dt = datetime.today()
    try:
        with open(file, "rb") as f:
            tags = exifread.process_file(f, details=False, stop_tag="DateTimeOriginal")
            dt_str = str(tags["EXIF DateTimeOriginal"])

        dt = datetime.strptime(dt_str, "%Y:%m:%d %H:%M:%S")
    except:
        pass
    finally:
        return dt


def get_file_time(file):
    ext = get_ext_lower(file)
    if "jpg" in ext or "jpeg" in ext:
        dt_jpg = get_jpg_date_time(file)
    else:
        dt_jpg = datetime.today()

    dtf = get_file_modified_time(file)

    today = datetime.today()

    # Use the older datetime of two. If both dates are same (and different time) then prefer dtjpg
    dt = dt_jpg if dt_jpg < dtf or dt_jpg.date() == dtf.date() else dtf
    #dt = dt_jpg if dt_jpg.date() != today.date() else dtf

    dt = dt.replace(microsecond=0) # precision till seconds only.

    if dt.date() == today.date():
        #raise RuntimeError("Error getting file time for %s, dtjpg=%s, dtf=%s" % (file, str(dtjpg), str(dtf)))
        return None

    return dt


def get_date_folder_month(month):
    if month in [1,2,3,4]:
        return "A"
    if month in [5,6,7,8]:
        return "B"
    if month in [9,10,11,12]:
        return "C"

    raise RuntimeError("getDateFolderMonth error for month %d" % month)


def get_src_dest_tuple_list(indir, outdir):
    print("Reading input files...")
    src_dest_tuple_list = []
    dest_to_src_map = {}
    dest_set = set()
    for dir_name, sub_dirs_list, files_list in os.walk(indir):
        sorted_files_list = sorted(files_list)
        for src_file in sorted_files_list:
            src_file = os.path.join(dir_name, src_file)
            print("Reading", src_file, "-")

            dt = get_file_time(src_file)
            if dt == None:
                print("IGNORED..")
                continue

            # WARNING: A change here also demands change in parsing below (parts = dest.split("-"))
            dest_file = dt.strftime("%Y-%m-%d_%H-%M-%S")
            print(dest_file)

            org_dest_file = dest_file
            i = 0
            suffix = ""
            while dest_file in dest_set:
                i += 1
                suffix = "D%03d" % i
                dest_file = "%s_%s" % (org_dest_file, suffix)

            if i > 0:
                print("Duplicate time found '%s' for '%s' and '%s', added suffix %s" % (org_dest_file, src_file, dest_to_src_map[org_dest_file], suffix))

            dest_set.add(dest_file)
            dest_to_src_map[dest_file] = src_file
            src_dest_tuple_list.append((src_file, dest_file))

    src_dest_tuple_list2 = []
    for src, dest in src_dest_tuple_list:
        parts = dest.split("-")
        # dateFolder = "%s_%s" % (parts[0], getDateFolderMonth(int(parts[1])))
        date_folder = parts[0]
        ext = get_ext_lower(src)
        # fileType = "pics" if is_pic_ext(ext) else "vids" if is_video_ext(ext) else "other"

        # src_dest_tuple_list2.append((src, os.path.join(outdir, fileType, date_folder, "%s.%s" % (dest, ext))))
        src_dest_tuple_list2.append((src, os.path.join(outdir, date_folder, "%s.%s" % (dest, ext))))

    return src_dest_tuple_list2


def create_dest_dirs(src_dest_tuple_list):
    print("Creating destination dirs...")
    dirs_to_create = set()
    for _, dest in src_dest_tuple_list:
        dirs_to_create.add(os.path.dirname(dest))

    for d in dirs_to_create:
        os.makedirs(d)


def move_files(src_dest_tuple_list):
    print("Moving files...")
    for src, dest in src_dest_tuple_list:
        print(src, "->", dest)
        if os.path.exists(dest):
            raise RuntimeError("Dest file %s already exists" % dest)
        shutil.move(src, dest)


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


def organize_files(indir, outdir):
    indir = os.path.normpath(indir)
    outdir = os.path.normpath(outdir)

    files = os.listdir(outdir)
    if files:
        raise RuntimeError("outdir %s is not empty" % outdir)

    src_dest_tuple_list = get_src_dest_tuple_list(indir, outdir)

    create_dest_dirs(src_dest_tuple_list)

    move_files(src_dest_tuple_list)


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


if __name__ == "__main__":
    IN_DIR = "D:\pics_and_vids"
    OUT_DIR = "D:\og"
    organize_files(IN_DIR, OUT_DIR)
