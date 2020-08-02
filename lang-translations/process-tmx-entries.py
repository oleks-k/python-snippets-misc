# misc TMX file processing
from lxml import etree
import csv
import sys


default_xml_namespace = "http://www.w3.org/XML/1998/namespace"
parser_xml = etree.XMLParser(strip_cdata=False)
tmx_file = sys.argv[1]
source_lang = sys.argv[2]
target_lang = sys.argv[3]
output_filename_no_ext = tmx_file[0:-4] + "_output_diff"
# tmx_file = "input.tmx"

root_tree = etree.parse(tmx_file, parser=parser_xml)
root = root_tree.getroot()

test = root.xpath(".//tuv[@xml:lang = '" + source_lang + "']")
tu_elems = root.xpath(".//tu")
# test_set = set()


def make_seg_elem_list(element_list):
    seg_elem_list = []
    test_list = []
    for elem in element_list:
        segments = elem.findall("seg")
        for seg_elem in segments:
            seg_elem_list.append(seg_elem)
            etree.strip_tags(seg_elem, "ph")
            test_list.append(seg_elem.text)
    return test_list, seg_elem_list


segments_source_and_target = []
for elem in tu_elems:
    if "usagecount" in elem.attrib:
        usage_count = elem.attrib["usagecount"]
    else:
        usage_count = 0
    source_tuv_in_tu = elem.xpath(".//tuv[@xml:lang = '" + source_lang + "']")
    target_tuv_in_tu = elem.xpath(".//tuv[@xml:lang = '" + target_lang + "']")
    seg_source = source_tuv_in_tu[0].find("seg")
    seg_target = target_tuv_in_tu[0].find("seg")
    etree.strip_tags(seg_source, "ph", "bpt", "ept")
    etree.strip_tags(seg_target, "ph", "bpt", "ept")
    segments_source_and_target.append([str(seg_source.text), str(seg_target.text), str(usage_count)])

only_source_segments = [item[0] for item in segments_source_and_target]


print("List length: " + str(len(segments_source_and_target)))
print("List length (only source): " + str(len(only_source_segments)))
print("Set length: " + str(len(set(only_source_segments))))

seen = {}
dupes = []
tracking_originals = {}
for x in segments_source_and_target:
    if x[0] not in seen:
        seen[x[0]] = 1
        tracking_originals[x[0]] = x
    else:
        if seen[x[0]] >= 1:
            if seen[x[0]] == 1:
                dupes.append(tracking_originals[x[0]])
            dupes.append(x)
        seen[x[0]] += 1

print(len(dupes))

write_string = ""
for dupe in dupes:
    write_string += dupe[0] + "\n" + dupe[1] + "\n" + "Usage count:" + dupe[2] + "\n\n"

# file = open('output.txt', 'w')
# file.write(write_string)
# file.close()

translation_diffs = []
source_seen = {}
for dupe_elem in dupes:
    if dupe_elem[0] not in source_seen:
        source_seen[dupe_elem[0]] = 1
    else:
        is_the_same = dupe_elem[1] == tracking_originals[dupe_elem[0]][1]
        if not is_the_same:
            if source_seen[dupe_elem[0]] == 1:
                translation_diffs.append(tracking_originals[dupe_elem[0]])
            translation_diffs.append([dupe_elem[0], dupe_elem[1], dupe_elem[2]])
        source_seen[dupe_elem[0]] += 1

translation_diffs.sort(key=lambda x01: x01[0])

write_string_diffs = ""
for diff_elem in translation_diffs:
    write_string_diffs += diff_elem[0] + "\n" + diff_elem[1] + "\n" + "Usage count:" + diff_elem[2] + "\n\n"

file = open(output_filename_no_ext + '.txt', 'w', encoding='utf-8')
file.write(write_string_diffs)
file.close()

with open(output_filename_no_ext + '.csv', 'w', newline='', encoding='utf-8') as csvfile:
    filewriter = csv.writer(csvfile, delimiter=',',
                            quotechar='\"', quoting=csv.QUOTE_MINIMAL)
    for diff_elem01 in translation_diffs:
        filewriter.writerow(diff_elem01)


print("Program finished.")
