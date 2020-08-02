# Scan Flare snippets created from PO files.
from lxml import etree
import os
import polib


# parser_html = lxml.html.HTMLParser(encoding="utf-8")
parser_xml = etree.XMLParser(strip_cdata=False)
dir_sep = "/"
project_dir = "."
content_dir = project_dir + dir_sep + "Content"
po_snippets_dir = "snippets-from-po"
snippet_dir = content_dir + dir_sep + po_snippets_dir
# scanning the PO file to determine the number of chars to the right of the limit.
po_input = polib.pofile("input.po")
ui_snippet_prefix = "ui-snip-txt-"
madcap_namespace = "http://www.madcapsoftware.com/Schemas/MadCap.xsd"

inline_tags = ["a", "abbr", "acronym", "b", "bdo", "big", "br", "button", "cite", "code", "dfn", "em", "i", "img",
               "input", "kbd", "label", "map", "object", "q", "samp", "script", "select", "small", "span", "strong",
               "sub", "sup", "textarea", "time", "tt", "var",
               "{" + madcap_namespace + "}snippetText",
               "{" + madcap_namespace + "}conditionalText"]

# parsing the source po file to get the keys for calculating the char number
po_key_list = []
po_key_list_trunc = []
for elem in po_input:
    temp_str = elem.msgid
    searchStr = '?\/\'\":*"<>|%# ,™[]{}+*!&()=.'
    if any((c in searchStr) for c in temp_str):
        for char in searchStr:
            temp_str = temp_str.replace(char, "_")
    po_key_list.append(temp_str.lower())
    po_key_list_trunc.append(temp_str.lower()[0:120])

# searching for duplicates
seen = set()
unique = []
duplicates = []
for x in po_key_list_trunc:
    if x in seen:
        duplicates.append(x)
    seen.add(x)


def indent(elem, level=0, more_sibs=False):
    i = "\n"
    empty_spaces = "    "
    if level:
        i += (level - 1) * empty_spaces
    num_children = len(elem)
    if num_children:
        if not elem.text or not elem.text.strip():
            if elem.getchildren()[0].tag not in inline_tags:
                elem.text = i + empty_spaces
                if level:
                    elem.text += empty_spaces
        count = 0
        for child in elem:
            if child.tag not in inline_tags:
                indent(child, level + 1, count < num_children - 1)
            count += 1
        if not elem.tail or not elem.tail.strip():
            elem.tail = i
            if more_sibs:
                elem.tail += empty_spaces
    else:
        if level and (not elem.tail or not elem.tail.strip()):
            elem.tail = i
            if more_sibs:
                elem.tail += empty_spaces


def write_root(root, filename):
    indent(root)
    result_str = etree.tostring(root, encoding="UTF-8")
    xml_declaration = b"<?xml version=\"1.0\" encoding=\"utf-8\"?>\n"
    result_str = xml_declaration + result_str
    output_file = open(filename, "wb")
    output_file.write(result_str)
    output_file.close()

# replacing extra special chars in src attributes of xrefs
def scan_files(path):
    global_snippet_list = []
    file_snippet_modified_list = []
    for root_dir, dirs, files in os.walk(path):
        root_dir = root_dir.replace(os.path.sep, dir_sep)
        for filename in files:
            if filename.endswith('.htm'):
                current_filepath = root_dir + dir_sep + filename
                root_tree = etree.parse(current_filepath, parser=parser_xml)
                root = root_tree.getroot()
                nsmap = root.nsmap
                nsmap_value = nsmap["MadCap"]
                snippetText_list = root.findall(".//{" + nsmap_value + "}snippetText")
                snippetBlock_list = root.findall(".//{" + nsmap_value + "}snippetBlock")
                file_snippet_list = snippetText_list + snippetBlock_list
                global_snippet_list += file_snippet_list
                searchStr = '&()=.'
                has_special_char = False
                has_no_ui_snippet_prefix = False
                for elem in file_snippet_list:
                    src_split = elem.attrib["src"].split(dir_sep)
                    # [0:-6] is to exclude the dot and the extension from search/replacement
                    tmp_string = src_split[-1][0:-6]
                    # Checking if the snippet path contains a char to replace
                    if any((c in searchStr) for c in tmp_string):
                        has_special_char = True
                        for char in searchStr:
                            tmp_string = tmp_string.replace(char, "_")
                        src_split[-1] = tmp_string + ".flsnp"
                        # TODO: move this outside of this loop (no time to test now)
                        elem.attrib["src"] = dir_sep.join(src_split)
                    # Checking if the snippet path starts with the ui snippet prefix
                    if po_snippets_dir in src_split and not tmp_string.startswith(ui_snippet_prefix):
                        has_no_ui_snippet_prefix = True
                        src_split[-1] = ui_snippet_prefix + tmp_string + ".flsnp"
                        # TODO: move this outside of this loop (no time to test now)
                        elem.attrib["src"] = dir_sep.join(src_split)
                if has_special_char or has_no_ui_snippet_prefix is True:
                    write_root(root, current_filepath)
                    for elem in file_snippet_list:
                        file_snippet_modified_list.append([current_filepath, elem])

    return file_snippet_modified_list, global_snippet_list


# This function replaces long legacy src links with shorter links
def scan_long_names(path):
    global_snippet_list = []
    file_snippet_modified_list = []
    for root_dir, dirs, files in os.walk(path):
        root_dir = root_dir.replace(os.path.sep, dir_sep)
        for filename in files:
            if filename.endswith('.htm'):
                current_filepath = root_dir + dir_sep + filename
                root_tree = etree.parse(current_filepath, parser=parser_xml)
                root = root_tree.getroot()
                nsmap = root.nsmap
                nsmap_value = nsmap["MadCap"]
                snippetText_list = root.findall(".//{" + nsmap_value + "}snippetText")
                snippetBlock_list = root.findall(".//{" + nsmap_value + "}snippetBlock")
                file_snippet_list = snippetText_list + snippetBlock_list
                global_snippet_list += file_snippet_list
                length_exceeded = False
                for elem in file_snippet_list:
                    src_filename = elem.attrib["src"].split("/")[-1]
                    cut_char_num = 100
                    filename_no_ext = src_filename.replace(".flsnp", "")
                    if len(filename_no_ext) > cut_char_num:
                        str_left = filename_no_ext[0:cut_char_num]
                        # getting the number of chars to the right from original keys (with replaced special chars)
                        for el01 in po_key_list:
                            # In the next line, -3 is to remove the numbers and the underscore from orig script (they are not in the orig keys)
                            if el01.startswith(filename_no_ext[:-3]):
                                num_char_to_right = len(el01[cut_char_num:])
                        # TODO: Make a list (in a separate function) of all po entries.
                        # Use starts with to get the matching one, then calculate the chars to the right.
                        filename_no_ext = str_left + str(num_char_to_right)
                        elem.attrib["src"] = elem.attrib["src"].replace(src_filename, filename_no_ext + ".flsnp")
                        length_exceeded = True
                if length_exceeded is True:
                    write_root(root, current_filepath)
                    for elem in file_snippet_list:
                        file_snippet_modified_list.append([current_filepath, elem])
    return file_snippet_modified_list, global_snippet_list


total_snippet_modified_list, total_snippet_list = scan_files(content_dir)

# Creating the list of used snippets
used_snippet_filepaths = set()
for elem in total_snippet_list:
    used_snippet_filepaths.add(snippet_dir + elem.attrib["src"].split("po_snippets")[-1])

# length_modified_list, total_length_list = scan_long_names(content_dir)


input("Press any key to end the program...")

