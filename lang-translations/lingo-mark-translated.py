# The script processes Lingo files. If all segments are translated, marks the whole file translated.
from lxml import etree
import sys
import os


parser_xml = etree.XMLParser(strip_cdata=False)
dir_to_process = sys.argv[1]
source_lang = sys.argv[2]
target_lang = sys.argv[3]
dir_sep = "/"
exclude_from_translation_value = "translation.exclude_from_translation"

def write_root(root, filename):
    result_str = etree.tostring(root, encoding="UTF-8")
    xml_declaration = b"<?xml version=\"1.0\" encoding=\"UTF-8\"?>\n"
    result_str = xml_declaration + result_str
    output_file = open(filename, "wb")
    output_file.write(result_str)
    output_file.close()


def replace_string_in_file(string1, string2, file_path):
    file = open(file_path, "r", encoding="UTF-8")
    filedata = file.read()
    file.close()
    filedata = filedata.replace(string1, string2)
    file = open(file_path, "w", encoding="UTF-8")
    file.write(filedata)
    file.close()


def scan_files(path):
    processed_files_count = 0
    marked_as_completed_count = 0
    for root_dir, dirs, files in os.walk(path):
        root_dir = root_dir.replace(os.path.sep, dir_sep)
        for filename in files:
            if filename.endswith('.xlf'):
                current_filepath = root_dir + dir_sep + filename
                root_tree = etree.parse(current_filepath, parser=parser_xml)
                root = root_tree.getroot()
                nsmap = root.nsmap
                nsmap_madcap_value = nsmap["MadCap"]
                nsmap_none_value = nsmap[None]
                file_elem = root.find("{" + nsmap_none_value + "}file")
                if file_elem.attrib["source-language"].lower() == source_lang.lower() and \
                        file_elem.attrib["target-language"].lower() == target_lang.lower():
                    mrk_elems = file_elem.findall(".//{" + nsmap_none_value + "}target/{" + nsmap_none_value + "}mrk")
                    is_translated = False
                    for elem in mrk_elems:
                        match_percent_value = elem.attrib["{" + nsmap_madcap_value + "}matchPercent"]
                        if "mtype" in elem.attrib and elem.attrib["mtype"] == "protected":
                            pass
                        # TODO: filter out the "excluded" elements with a condition like this:
                        # elif "{" + nsmap_madcap_value + "}conditions" in elem.attrib and elem.attrib["{" + nsmap_madcap_value + "}conditions"] == exclude_from_translation_value:
                        # This condition is in the seg-source element, so it requires more work.
                        elif int(match_percent_value) < 100:
                            is_translated = False
                            break
                        else:
                            is_translated = True
                    processed_files_count += 1
                    if is_translated == True:
                        original_trans_status = "MadCap:translationStatus=\"" + root.attrib["{" + nsmap_madcap_value + "}translationStatus"] + "\""
                        new_trans_status = "MadCap:translationStatus=\"completed\""
                        root.attrib["{" + nsmap_madcap_value + "}translationStatus"] = "completed"
                        replace_string_in_file(original_trans_status, new_trans_status, current_filepath)
                        marked_as_completed_count += 1
    return processed_files_count, marked_as_completed_count


files_count = scan_files(dir_to_process)
file = open("processed_" + str(source_lang) + "_" + str(target_lang) + '.txt', 'w', encoding='utf-8')
file.write(str(files_count))
file.close()

print("Program finished.")
