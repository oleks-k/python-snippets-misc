import sys
import os
import pathlib
import json
from lxml import etree
from collections import Counter
import pyperclip


parser_xml = etree.XMLParser(strip_cdata=False)
parser_html = etree.HTMLParser()
dir_sep = "/"
madcap_namespace = "http://www.madcapsoftware.com/Schemas/MadCap.xsd"
madcap_nsmap = {"MadCap": madcap_namespace}
config_file = sys.argv[1]

with open(config_file, encoding="utf-8") as data_file:
    json_data_config = json.load(data_file)

product_manual_source_dir = json_data_config['manual_source_dir'].replace('\\', dir_sep)
product_manual_toc_filepath = product_manual_source_dir + '/docdata/toc.json'

with open(product_manual_toc_filepath, encoding="utf-8") as data_file:
    json_data_toc = json.load(data_file)

flare_root_dir = json_data_config['flare_root_dir'].replace('\\', dir_sep)
flare_dir_content = flare_root_dir + 'Content/'
flare_dir_project = flare_root_dir + 'Project/'
product_manual_target_dir = flare_dir_content + 'product-manual/'
tag_and_class_delimiter = ', '
elements_to_remove = json_data_config['elements_to_remove']

all_product_manual_topics = json_data_toc['children']

inline_tags = ["a", "abbr", "acronym", "b", "bdo", "big", "br", "button", "cite", "code", "dfn", "em", "i", "img",
               "input", "kbd", "label", "map", "object", "q", "samp", "script", "select", "small", "span", "strong",
               "sub", "sup", "textarea", "time", "tt", "var",
               "{" + madcap_namespace + "}snippetText",
               "{" + madcap_namespace + "}snippetBlock",
               "{" + madcap_namespace + "}conditionalText",
               "{" + madcap_namespace + "}xref"]


def check_create_folder(directory):
    pathlib.Path(directory).mkdir(parents=True, exist_ok=True)


def indent_xml(elem, level=0, more_sibs=False):
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
                indent_xml(child, level + 1, count < num_children - 1)
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


def xml_create_flare_root(div_section_from_product):
    root = etree.Element("html", nsmap=madcap_nsmap)
    root.text = '\n'
    etree.SubElement(root, "head").tail = '\n'
    div_section_from_product.tag = 'body'
    del div_section_from_product.attrib['class']
    root.append(div_section_from_product)
    return root


def write_root(root, filename):
    indent_xml(root)
    result_str = etree.tostring(root, encoding="UTF-8")
    xml_declaration = b"<?xml version=\"1.0\" encoding=\"utf-8\"?>\n"
    result_str = xml_declaration + result_str
    # Making sure that the target dir exists
    check_create_folder(pathlib.Path(filename).parent)
    output_file = open(filename, "wb")
    output_file.write(result_str)
    output_file.close()

toc_attributes = {'Version': '1'}
flare_toc_root = etree.Element("CatapultToc", attrib=toc_attributes)
current_toc_parent_elem = flare_toc_root

def add_topic_to_toc(parent, topic_link):
    attributes = {'Title': '[%=System.LinkedTitle%]', 'Link': topic_link}
    new_toc_entry = etree.SubElement(parent, 'TocEntry', attrib=attributes)
    return new_toc_entry

def generate_flare_topic(product_toc_item):
    global current_toc_parent_elem
    filename_no_ext = product_toc_item['link']
    product_filepath = product_manual_source_dir + filename_no_ext + '.html'
    source_root_tree = etree.parse(product_filepath, parser=parser_html)
    source_root_element = source_root_tree.getroot()
    content_div = source_root_element.xpath("//div[@class='section']")[0]
    source_children = list(content_div.getchildren())
    for elem in source_children:
        if elem.tag is not etree.Comment:
            if elem.attrib.has_key('class'):
                tag_and_class = tag_and_class_delimiter.join([elem.tag, elem.attrib['class'].strip()])
            else:
                tag_and_class = elem.tag
            if tag_and_class in elements_to_remove:
                elem.getparent().remove(elem)
        else:
            elem.getparent().remove(elem)
    flare_root = xml_create_flare_root(content_div)
    write_root(flare_root, product_manual_target_dir + filename_no_ext + '.htm')
    toc_entry_link_rel_path = '/' + os.path.relpath(product_manual_target_dir, flare_root_dir).replace('\\', dir_sep) + '/' + filename_no_ext + '.htm'
    new_toc_entry = add_topic_to_toc(current_toc_parent_elem, toc_entry_link_rel_path)
    if product_toc_item['children'] is not None:
        previous_toc_parent_elem = current_toc_parent_elem
        current_toc_parent_elem = new_toc_entry
        for item in product_toc_item['children']:
            generate_flare_topic(item)
        current_toc_parent_elem = previous_toc_parent_elem


# Going through all level 1 elements in TOC
for child in all_product_manual_topics:
    generate_flare_topic(child)


print('Script finished.')
