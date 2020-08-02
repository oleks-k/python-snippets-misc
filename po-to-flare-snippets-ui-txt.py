# Convert PO files to Flare snippets
import polib
from lxml import etree
import os
import datetime
import string
import pathlib
import html
import lxml.html
import sys


parser_xml = etree.XMLParser(strip_cdata=False)
# The script gets the PO file as the first argument
po_en = polib.pofile(sys.argv[1])
# target_folder = "./Output/snippets_test/"
dir_sep = "/"
project_dir = "."
content_dir = project_dir + dir_sep + "Content"
ui_snippet_dir = "ui_txt"
target_folder = "./Content/" + ui_snippet_dir + "/"

alphabet = string.ascii_lowercase
mtxt_string = "{MTXT}"
ui_snippet_prefix = "uitxt_"
cut_char_num = 100

date_time = datetime.datetime.now().strftime("%Y.%m.%d-%H.%M")
parser_html = lxml.html.HTMLParser(encoding="utf-8")
products_attrib = "products"

flare_cond_attrib = "MadCap:conditions"
madcap_namespace = "http://www.madcapsoftware.com/Schemas/MadCap.xsd"

inline_tags = ["a", "abbr", "acronym", "b", "bdo", "big", "br", "button", "cite", "code", "dfn", "em", "i", "img",
               "input", "kbd", "label", "map", "object", "q", "samp", "script", "select", "small", "span", "strong",
               "sub", "sup", "textarea", "time", "tt", "var",
               "{" + madcap_namespace + "}snippetText",
               "{" + madcap_namespace + "}conditionalText"]


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


# This function scans all files and returns a list of links to all used snippets
def scan_files(path):
    global_snippet_list = []
    filenames = set()
    for root_dir, dirs, files in os.walk(path):
        root_dir = root_dir.replace(os.path.sep, dir_sep)
        for filename_tmp in files:
            if filename_tmp.endswith('.htm'):
                current_filepath = root_dir + dir_sep + filename_tmp
                root_tree = etree.parse(current_filepath, parser=parser_xml)
                root = root_tree.getroot()
                nsmap = root.nsmap
                nsmap_value = nsmap["MadCap"]
                snippetText_list = root.findall(".//{" + nsmap_value + "}snippetText")
                snippetBlock_list = root.findall(".//{" + nsmap_value + "}snippetBlock")
                file_snippet_list = snippetText_list + snippetBlock_list
                global_snippet_list += file_snippet_list
            if filename_tmp.endswith('.flsnp') and (ui_snippet_dir in root_dir):
                filenames.add(filename_tmp.split(dir_sep)[-1][0:-6])
    # Extracting only unique links
    for elem in global_snippet_list:
        filenames.add(elem.attrib["src"].split(ui_snippet_dir)[-1].split(dir_sep)[-1][0:-6])
    return filenames


def write_root(root, filename):
    indent(root)
    result_str = etree.tostring(root, encoding="UTF-8")
    # TODO: unescaping &lt; and &gt; because method="html" does not unescape them
    # result_str_decoded = result_str.decode("UTF-8")
    # result_str = html.unescape(result_str_decoded)
    # result_str = result_str.encode()
    xml_declaration = b"<?xml version=\"1.0\" encoding=\"utf-8\"?>\n"
    result_str = xml_declaration + result_str
    output_file = open(filename, "wb")
    output_file.write(result_str)
    output_file.close()


def check_create_folder(directory):
    pathlib.Path(directory).mkdir(exist_ok=True)


# Using lxml.html.fromstring() results in elements with tails
# This function does extra processing on tails
# para should be XML
# NOTE: This function is not used currently, but it's here just in case.
def process_para(para):
    para_el = lxml.html.fragments_fromstring(para, parser=parser_html)
    # print("test")
    for elem in para_el:
        if elem.tail != None:
            new_elems = []
            if elem.tag in inline_tags:
                pass
            else:
                new_el = etree.Element("p")
                new_el.text = elem.tail
                new_elems.append(new_el)
                elem.tail = None
                temp_el = elem
                # TODO: make this a function, also used in the loop
                inline_elems = []
                while temp_el.getnext() != None and temp_el.getnext().tag in inline_tags:
                    inline_elems.append(temp_el.getnext())
                    temp_el = temp_el.getnext()
                for a_elem in inline_elems:
                    new_el.append(a_elem)

            if len(new_elems) > 0:
                for new_elem in new_elems:
                    elem.addnext(new_elem)
    return para_el[0].getparent()


# string01 is the legacy text key, string02 is msgstr
def create_html_root(string01, string02):
    my_nsmap = {"MadCap": "http://www.madcapsoftware.com/Schemas/MadCap.xsd"}
    root = etree.Element("html", nsmap=my_nsmap)
    root_head = etree.SubElement(root, "head")
    root_body = etree.SubElement(root, "body")
    # Adding msgid and msgstr as metadata
    meta_mtxt = etree.SubElement(root_head, "meta")
    meta_mtxt.attrib["name"] = "legacy_mtxt"
    if mtxt_string in string02:
        meta_mtxt.attrib["content"] = mtxt_string
        string02 = string02.replace(mtxt_string, "")
    else:
        meta_mtxt.attrib["content"] = "NONE"
    meta_legacy_id = etree.SubElement(root_head, "meta")
    meta_legacy_id.attrib["name"] = "legacy_msgid"
    meta_legacy_id.attrib["content"] = string01

    # TODO: put replacements in a function
    temp_str = string02.replace("{lb}{lb}", "{para}")
    temp_str = temp_str.replace("{lb}", "<br />")
    temp_str = temp_str.replace("{b}", "<b>")
    temp_str = temp_str.replace("{/b}", "</b>")
    # Testing START
    temp_str = temp_str.replace("{para}", "<p>")
    # Doing the try here because some msgstr values are like this: "<"
    try:
        content_elem = lxml.html.fromstring(temp_str)
    except:
        content_elem = lxml.html.fromstring("<p>" + temp_str + "</p>")
    # This "if" is because the fromstring method adds an extra div if there's more than 1 tag in the source
    if len(content_elem) == 0 or content_elem.tag is not "div" or content_elem.text is not None:
        root_body.append(content_elem)
    else:
        if len(content_elem.attrib) > 0:
            root_body.append(content_elem)
        else:
            for elem in content_elem:
                root_body.append(elem)
    # Testing END
    # Processing the attributes
    for element in root.iter():
        if products_attrib in element.attrib:
            # TODO: What if the products attribute contains multiple values
            nsmap_value = element.nsmap["MadCap"]
            if products_attrib_val_value_1 in element.attrib[products_attrib]:
                element.attrib["{" + nsmap_value + "}conditions"] = flare_cond_val_value_1
            element.attrib.pop(products_attrib)
    return {"root": root, "root_head": root_head}


snippets_used = scan_files(content_dir)

check_create_folder(target_folder)

name_list = []
for entry in po_en:
    current_root = create_html_root(entry.msgid, entry.msgstr)

    filename = entry.msgid
    # removing special chars from filename
    searchStr = '?\/\'\":*"<>|%# ,™[]{}+*!&()=.'
    if any((c in searchStr) for c in filename):
        for char in searchStr:
            filename = filename.replace(char, "_")
    if len(filename) > cut_char_num:
        str_left = filename[0:cut_char_num]
        num_char_to_right = len(filename[cut_char_num:])
        filename = str_left + str(num_char_to_right)
    name_lower = filename.lower()
    name_list.append(name_lower)
    counter = name_list.count(name_lower)
    if counter > 1:
        name_lower += "_n" + str(counter - 1)
    name_lower += ".flsnp"
    first_char = name_lower[0]
    if first_char not in alphabet:
        first_char = "_"
    name_lower = ui_snippet_prefix + name_lower
    current_folder = target_folder + first_char + dir_sep
    check_create_folder(current_folder)
    output_location = current_folder + name_lower

    write_root(current_root["root"], output_location)


print(len(name_list))
print("Program finished")
