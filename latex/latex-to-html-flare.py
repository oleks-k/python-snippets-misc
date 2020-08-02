'''
Some Latex to Flare code snippets.
'''
import sys
import os
import subprocess
import pathlib
import shutil
import json
from lxml import etree
from collections import Counter
import pyperclip
import copy
import logging
import string

logging.basicConfig(level=logging.INFO, filename='latex_to_flare.log', filemode='w')
parser_xml = etree.XMLParser(strip_cdata=False)
dir_sep = "/"
config_file = sys.argv[1]
config_file_graphics_items = 'config_file_graphics_items.json'
config_file_graphics_size_map = 'config_file_graphics_size_map.json'
with open(config_file_graphics_size_map, encoding="utf-8") as data_file:
    graphics_size_map = json.load(data_file)
tmp_prefix = 'temp1_'
tex_files_dirname = 'latex-files'
tmp_root_dir = tmp_prefix + tex_files_dirname
# Reading the config and the source TOC from json.
with open(config_file, encoding="utf-8") as data_file:
    json_data = json.load(data_file)
language = json_data['config']['language']
language_en = 'en'
source_root_dir = json_data['config']['source_root_dir'].replace('\\', dir_sep)
flare_root_dir = json_data['config']['flare_root_dir'].replace('\\', dir_sep)
flare_dir_content = flare_root_dir + 'Content/from-latex/'
flare_dir_project = flare_root_dir + 'Project/'
flare_dir_snippets_tex = flare_dir_content + 'snippets-latex/'

pandoc_path = 'pandoc'
pandoc_logs_dir = 'pandoc_logs'
madcap_namespace = "http://www.madcapsoftware.com/Schemas/MadCap.xsd"
madcap_nsmap = {"MadCap": madcap_namespace}
labels_from_tex = {}
mc_cond_attrib_name = '{' + madcap_namespace + '}conditions'
mc_snippet_block_tag = '{' + madcap_namespace + '}snippetBlock'
mc_snippet_text_tag = '{' + madcap_namespace + '}snippetText'
mc_xref_tag = '{' + madcap_namespace + '}xref'
mc_keyword_tag = '{' + madcap_namespace + '}keyword'
mc_keyword_textcolor_value = 'madcap-keyword'
# mc_textcolor_paragraph_value = 'tex-paragraph'
mc_p_subtopic_class = 'subtopic'
temp_tag_to_strip = 'stripthistag'
newcommand = '\\newcommand'
repl_string_start = 'TEXCOMMSTART'
repl_string_end = 'TEXCOMMEND'
texlabel = 'TEXLABEL'

latex_conditions = {
    "product":
        [
            "prod1",
            "prod2"
        ]
}

inline_tags = ["a", "abbr", "acronym", "b", "bdo", "big", "br", "button", "cite", "code", "dfn", "em", "i", "img",
               "input", "kbd", "label", "map", "object", "q", "samp", "script", "select", "small", "span", "strong",
               "sub", "sup", "textarea", "time", "tt", "var",
               "{" + madcap_namespace + "}snippetText",
               "{" + madcap_namespace + "}snippetBlock",
               "{" + madcap_namespace + "}conditionalText",
               "{" + madcap_namespace + "}xref"]


# Converting the string latex input into string output.
# Runs pandoc as subprocess and reads the console output of pandoc.
def convert_from_string(source_latex):
    source_latex_encoded = source_latex.encode('utf-8')
    args = ['pandoc', '--from=latex', '--to=html5']
    p = subprocess.Popen(
        args,
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE)
    # FROM bebraw/pypandoc: not 'None' indicates that the process already terminated
    if not (p.returncode is None):
        raise RuntimeError(
            'Pandoc terminated with exitcode "%s" before receiving input: %s' % (p.returncode, p.stderr.read())
        )

    try:
        stdout, stderr = p.communicate(source_latex_encoded)
    except OSError:
        raise RuntimeError('Pandoc terminated with exitcode "%s" during conversion.' % (p.returncode))

    try:
        stdout = stdout.decode('utf-8')
    except UnicodeDecodeError:
        # Just in case pandoc ouputs not utf-8 for some reason
        raise RuntimeError('Pandoc output was not utf-8.')

    if p.returncode != 0:
        raise RuntimeError(
            'Pandoc terminated with exitcode "%s" during conversion: %s' % (p.returncode, stderr)
        )
    return stdout.replace('\r\n', '\n')


# Just beautifies xml.
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


def check_create_folder(directory):
    pathlib.Path(directory).mkdir(parents=True, exist_ok=True)


# This function returns the value between given markers. If there are no markers in input, returns None.
# Assumptions: There are no nested or unbalanced markers.
def get_value_between_markers(input_string, marker_start, marker_end):
    ind_start = input_string.find(marker_start)
    if ind_start == -1:
        return None
    else:
        ind_end = input_string.find(marker_end)
        return input_string[ind_start + len(marker_start): ind_end]


def findall(full_string, substring):
    occurrences = []
    i = full_string.find(substring)
    while i != -1:
        occurrences.append(i)
        i = full_string.find(substring, i + 1)
    return occurrences


# Returns the command before the given position
def get_prev_comm_string(source_text, position, substring='\\', include_substring=False):
    ind_prev = source_text.rfind(substring, 0, position)
    offset = int(not include_substring) * len(substring)
    prev_string = source_text[ind_prev + offset:position].strip()
    return prev_string, ind_prev


# Returns the next command after the given position (not after the command at the given position)
# Also returns the next token's index and the token that ends the command definition (defined in end_of_comm)
# TODO: write an example of how it works
def get_next_comm_string(source_text, position, include_start_substring=False, include_token=False):
    start_substring = '\\'
    end_of_comm = ['\\', '{', '}', '[', ' ', '\n', '\t']
    ind_next_delimiter = len(source_text)
    current_token = ''
    for x in end_of_comm:
        ind = source_text.find(x, position + 1)
        if ind != -1 and ind < ind_next_delimiter:
            ind_next_delimiter = ind
            current_token = x
            # In case a command ends with '{}', write it in current_token
            if current_token == '{' and source_text[ind + 1] == '}':
                current_token = '{}'
    offset_start = int(not include_start_substring) * len(start_substring)
    offset_end = int(include_token) * len(current_token)
    # TODO: how to deal with \\. The second backslash is the command and should not be treated as a command start.
    next_string = source_text[position + offset_start:ind_next_delimiter + offset_end].strip()
    return next_string, ind_next_delimiter, current_token


def find_nth(full_string, substring, n):
    start = full_string.find(substring)
    if full_string.count(substring) < n:
        print('WARNING: Possibly unbalanced start/end markers: ' + full_string)
        logging.warning('Possibly unbalanced start/end markers: ' + full_string)
        input()
        return len(full_string) - 1
    else:
        while start >= 0 and n > 1:
            start = full_string.find(substring, start + len(substring))
            n -= 1
        return start


# This function replaces a substring in a string searching from a certain index
# The function does only 1 replacement
def str_replace_from_index(text, string_to_repl, string_repl_with, index=0):
    part_1 = text[:index]
    part_2 = text[index:]
    part_2 = part_2.replace(string_to_repl, string_repl_with, 1)
    return part_1 + part_2


def bracket_extra_space(full_text, end_marker):
    bracket_space = 0
    if full_text[end_marker:end_marker + 2] == '{}':
        bracket_space = 2
    return bracket_space


# Returns the list of start and end indices for the given start and end substrings
# in the given text string. If there are nested start-end pairs, the function returns
# the indices for the parent pairs.
# NOTE: the end index is the end of the substring, not the index of the beginning of the end string
def get_indices_start_end(text, start_string, end_string):
    copy_file_text = text
    marker_end = 0
    marker_text_cut = 0
    indices = []
    while copy_file_text.find(start_string) >= 0:
        marker_start = copy_file_text.find(start_string)
        marker_end = copy_file_text.find(end_string) + len(end_string)
        bracket_space = bracket_extra_space(copy_file_text, marker_end)
        marker_end = marker_end + bracket_space
        # Searching for the closing command
        string_part = copy_file_text[marker_start:marker_end]
        start_string_count = string_part.count(start_string)
        end_string_count = string_part.count(end_string)
        while start_string_count - end_string_count > 0:
            marker_end = marker_end + find_nth(copy_file_text[marker_end:], end_string,
                                               start_string_count - end_string_count) + len(end_string)
            bracket_space = bracket_extra_space(copy_file_text, marker_end)
            marker_end = marker_end + bracket_space
            string_part = copy_file_text[marker_start:marker_end]
            start_string_count = string_part.count(start_string)
            end_string_count = string_part.count(end_string)        
        indices.append([marker_start + marker_text_cut, marker_end + marker_text_cut])
        marker_text_cut += marker_end
        # Reevaluating the string part after finding the new end
        copy_file_text = copy_file_text[marker_end:]
    return indices


# This function returns a list of strings containing \ifx ... \fi{} substrings
# It returns the original strings (to find them in the source text), and the new strings,
# So that you can replace the original ones.
# Note: it also runs process_else on the new strings
def extract_content(file_text, com_start, com_end, how_many_to_return=-1, do_process_else=False):
    copy_file_text = file_text
    string_parts_original = []
    string_parts_new = []
    indices = get_indices_start_end(copy_file_text, com_start, com_end)
    if how_many_to_return:
        for i, ind in enumerate(indices):
            string_part = copy_file_text[ind[0]:ind[1]]
            string_parts_original.append(string_part)
            if do_process_else:
                string_parts_new.append(process_else(string_part))
            else:
                string_parts_new.append(string_part)
            if i == how_many_to_return - 1:
                break
    return string_parts_original, string_parts_new


def process_else_ifx(text):
    new_text = text
    else_tag = '\\else'
    while else_tag in new_text:
        ind_else = new_text.find(else_tag)
        new_text = str_replace_from_index(new_text, else_tag, '\\fi', ind_else)
        ind_fi = get_indices_start_end(new_text[ind_else:], '\\ifx', '\\fi')[0][1]
        # Removing '\\fi' that goes further after the '\\fi' that we've just added
        # TODO: strip the space to the right (or left?) from the removed \\fi
        ind_next_fi = ind_else + ind_fi + new_text[ind_else + ind_fi:].find('\\fi')
        part_1 = new_text[:ind_next_fi].rstrip()
        part_2 = new_text[ind_next_fi:]
        part_2 = part_2.replace('\\fi', '', 1)
        new_text = part_1 + part_2
    return new_text


# This function replaces the \else{} clause with \else\ifx with the exact set of conditions
def process_else(text):
    else_tag = '\\else{}'
    text_new = text
    while else_tag in text_new:
        ind_else = text_new.find(else_tag)
        ind_ifx = text_new.rfind('\\ifx', 0, ind_else)
        current_cat = get_next_comm_string(text_new, get_next_comm_string(text_new, ind_ifx)[1])
        conditions_in_prev_ifx = {}
        conditions_in_prev_ifx[current_cat[0]] = []
        current_cond = get_next_comm_string(text_new, current_cat[1])
        conditions_in_prev_ifx[current_cat[0]].append(current_cond[0])
        while get_prev_comm_string(text_new, ind_ifx)[0] == 'else':
            ind_ifx = text_new.rfind('\\ifx', 0, ind_ifx)
            tex_cat = get_next_comm_string(text_new, get_next_comm_string(text_new, ind_ifx)[1])
            tex_cond = get_next_comm_string(text_new, tex_cat[1])
            if tex_cat[0] in conditions_in_prev_ifx:
                conditions_in_prev_ifx[tex_cat[0]].append(tex_cond[0])
            else:
                conditions_in_prev_ifx[tex_cat[0]] = []
                conditions_in_prev_ifx[tex_cat[0]].append(tex_cond[0])
        # Now when I have the list of conditions for else{}, I replace it with ifx
        # the my_or string is for putting multiple conditions in one string
        my_or = '_MYOR_'
        # Creating a string with conditions to exclude separated by my_or
        conditions_to_join = []
        # SIMPLIFICATION: Only handling one category
        for elem in conditions_in_prev_ifx:
            for condition in latex_conditions[elem]:
                if condition not in conditions_in_prev_ifx[elem]:
                    conditions_to_join.append(condition)
        conditions_joined = my_or.join(conditions_to_join)
        # SIMPLIFICATION: Only handling one category
        text_new = str_replace_from_index(text_new, else_tag, '\\else\\ifx\\' + list(conditions_in_prev_ifx.keys())[0]
                                          + '\\' + conditions_joined, ind_else)
        # Adding an extra '\fi'
        text_new = str_replace_from_index(text_new, '\\fi', '\\fi\\fi', ind_else)
    return text_new


def replace_ifx_with_textcolor(text, start_tag, end_tag, replacement_tag):
    new_text = text
    indices = get_indices_start_end(new_text, start_tag, end_tag)
    # TODO: handle nested conditions
    for ind_pair in reversed(indices):
        # Replacing from the end of string (to avoid index shift)
        new_text = str_replace_from_index(new_text, end_tag, '}', ind_pair[1] - len(end_tag))
        # Getting the index of the end of the ifx expression
        next_ind = ind_pair[0]
        for i in range(3):
            next_ind = get_next_comm_string(text, next_ind)[1]
        bracket_offset = bracket_extra_space(new_text, next_ind)
        substring_to_replace = new_text[ind_pair[0]: next_ind + bracket_offset]
        replacement_tag_option = substring_to_replace[:len(substring_to_replace) - bracket_offset].replace('\\ifx\\',
                                                                                                           '')
        replacement_tag_option = replacement_tag + '{IFXCOND_' + replacement_tag_option.replace('\\', '_SEP_') + '}{'
        # Stripping the whitespace from what's inside ifx commands
        part_left = new_text[:ind_pair[0] + len(substring_to_replace)]
        part_right = new_text[ind_pair[0] + len(substring_to_replace):]
        ind_nonwhitespace = next(i2 for i2, char in enumerate(part_right) if char not in string.whitespace)
        if '\n' in part_right[:ind_nonwhitespace]:
            part_right = part_right.lstrip()
        ind_closing_br = part_right.find('}')
        if '{' in part_right[:ind_closing_br]:
            ind_closing_br = find_nth(part_right, '}', 2)
        part_before_br = part_right[:ind_closing_br]
        part_after_br = part_right[ind_closing_br:]
        if '\n' in part_before_br[len(part_before_br.rstrip()) - len(part_before_br):]:
            part_before_br = part_before_br.rstrip()
        part_right = part_before_br + part_after_br
        new_text = part_left + part_right
        # End of striping whitespace
        new_text = str_replace_from_index(new_text, substring_to_replace, replacement_tag_option, ind_pair[0])
        # Handling the case where only \item element is inside \ifx
        # NOTE: this workaround will not work if there is more than 1 \item inside,
        # but in our project it's not more than 1
        if '\\item' in new_text:
            inside_condition = new_text[len(replacement_tag_option):].lstrip()
            if inside_condition.startswith('\\item'):
                if new_text.count('\\item') > 1:
                    print('WARNING: More than 1 \\item commands inside \\ifx. Check the list element in ' + text + '\n')
                    logging.warning('WARNING: More than 1 \\item commands inside \\ifx. Check the list element in ' + text)
                else:
                    # NOTE: It's a hack for one occurrence of ifx around \item[] in preface_en. The difference is [.
                    # This might not work for other occurrences (that's why I'm printing a warning just in case)
                    if inside_condition.startswith('\\item['):
                        hack_text = replacement_tag_option[len('\\textcolor{'):-len('}{')].replace('_', '\\_')
                        new_text = inside_condition[:-1].rstrip() + hack_text + 'IFXCONDEND'
                        print('CAUTION: \\item[] hack. Check output: ' + new_text)
                        logging.info('CAUTION: \\item[] hack. Check output: ' + new_text)
                    else:
                        item_split = new_text.split('\\item')
                        new_text = '\\item' + item_split[0].rstrip() + item_split[1].lstrip()
    if start_tag in new_text:
        new_text = replace_ifx_with_textcolor(new_text, start_tag, end_tag, replacement_tag)
    return new_text


# textcolor requires the second argument, I'm adding it here
# also adding texref_ at the beginning of the ref value for easier postprocessing
# ind_part_in_brackets: The index of the part in brackets that the function should process. For example:
# If you run this function with ind_part_in_brackets=1 on \command{partIndex0}{partIndex1}, the function processes
# partIndex1.
def change_command_value(text, command, string_start, string_end, keep_brackets=False, escape_underscore=False,
                         bracket_left='{', bracket_right='}', ind_part_in_brackets=0, replace_comm_def_with_value=False):
    new_text = text
    ref_indices = findall(new_text, command)
    ref_ind_and_string_parts = []
    for ind in ref_indices:
        current_parts = extract_content(new_text[ind:], bracket_left, bracket_right, ind_part_in_brackets + 1, do_process_else=True)
        part_ind_from = 1 * int(not keep_brackets)
        current_part_new = current_parts[0][ind_part_in_brackets]
        if escape_underscore:
            current_part_new = current_part_new.replace('_', '\\_')
        part_ind_to = len(current_part_new) - 1 * int(not keep_brackets)
        current_parts[1][ind_part_in_brackets] = string_start + current_part_new[part_ind_from:part_ind_to] + string_end
        ref_ind_and_string_parts.append([ind, current_parts])
    if replace_comm_def_with_value:
        for elem in reversed(ref_ind_and_string_parts):
            new_text = str_replace_from_index(new_text, command + ''.join(elem[1][0]), elem[1][1][ind_part_in_brackets], elem[0])
    else:
        for elem in reversed(ref_ind_and_string_parts):
            new_text = str_replace_from_index(new_text, elem[1][0][ind_part_in_brackets], elem[1][1][ind_part_in_brackets], elem[0])
    return new_text, ref_ind_and_string_parts


def process_unit_comm(text):
    new_text = text
    for command in json_data['config']['unit_commands']:
        new_text = change_command_value(new_text, '\\' + command + '[', '{', '}', escape_underscore=False,
                                        bracket_left='[', bracket_right=']')[0]
    return new_text


def add_brackets_to_else_without_ifx(text):
    new_text = text
    indices = findall(new_text, '\\else')
    for ind in reversed(indices):
        if not new_text[ind + len('\\else'):].startswith(('{}', '\\ifx')):
            new_text = str_replace_from_index(new_text, '\\else', '\\else{}', ind)
    return new_text


def process_newcommand(text):
    newcommands_all = change_command_value(text, newcommand, '', '', escape_underscore=False, keep_brackets=True,
                                           ind_part_in_brackets=1)
    newcommands_extract = []
    for elem in newcommands_all[1]:
        newcommands_extract.append([elem[0], elem[1][0][0], elem[1][0][1]])
    commands_to_leave = []
    commands_to_replace = []
    for elem in newcommands_extract:
        ind_first_arg = elem[0] + len(newcommand + elem[1])
        if text[ind_first_arg:ind_first_arg + 1] == '[':
            commands_to_leave.append(elem[1])
        else:
            commands_to_replace.append(elem[1])
    newcommand_data = {
        "commands_to_leave": commands_to_leave,
        "commands_to_replace": commands_to_replace,
        "newcommands_extract": newcommands_extract,
        "original_file_content": text
    }
    return newcommand_data


# This function extracts and saves the \newcommand definitions. The beginning is mostly a copy of preproc().
def extract_newcomm_defs(toc_entry):
    source_file_path = source_root_dir + toc_entry["path"]
    # Just to ensure that path has / as the dir separator
    source_file_path = source_file_path.replace('\\', dir_sep)
    source_filename = source_file_path.split('/')[-1]
    source_filename_noext = source_filename[0:-4]
    # Creating the temporary directory for storing the preprocessed tex files.
    dirpath_part_after_tex_files = source_file_path.split(tex_files_dirname)[-1].replace(source_filename, '')
    tmp_current_dir = tmp_root_dir + dirpath_part_after_tex_files
    check_create_folder(tmp_current_dir)
    # Just copying the file to a tmp directory.
    tmp_tex_filepath = tmp_current_dir + source_filename_noext + '.tex'
    # Start preprocessing
    with open(source_file_path, 'r', encoding='utf-8') as file:
        file_lines = file.readlines()
    # command_list_in_cur_file = helper_get_list_of_commands(file_lines).most_common()
    # Remove commented lines and empty commands (for example, else{}\fi{})
    cleaned_lines = clean_up_lines(file_lines)
    new_file_content = ''.join(cleaned_lines)
    with open(tmp_tex_filepath, 'w', encoding='utf-8') as file:
        file.write(new_file_content)
    # Adding {} to \else where \else does not end with either {} or \ifx
    new_file_content = add_brackets_to_else_without_ifx(new_file_content)
    # PREAMBLE START
    if ('type' in toc_entry) and (toc_entry['type'] == 'preamble'):
        # \newcommand: Preprocessing the values (second {}) of \newcommand
        newcommand_data = process_newcommand(new_file_content)
        with open(tmp_tex_filepath.replace('.tex', '.json'), 'w', encoding='utf-8') as file:
            json.dump(newcommand_data, file, indent=4)


# commands must be a dict
def macros_to_plaintext(text, commands):
    text_new = text
    comms_list = commands['all_comms_to_replace']
    placeholder_start = 'PLACEHOLDSTART'
    placeholder_end = 'PLACEHOLDEND'
    # This replacement is to ensure that newcommand definitions are not replaced
    ph_repl = {}
    for i, comm in enumerate(comms_list):
        ph_repl[placeholder_start + str(i) + placeholder_end] = newcommand + comm
        text_new = text_new.replace(newcommand + comm, placeholder_start + str(i) + placeholder_end)
    for comm in comms_list:
        # Doing two replacements because commands end/end not with '{}'
        text_new = text_new.replace(comm[1:-1] + '{}', repl_string_start + comm[2:-1] + repl_string_end)
        text_new = text_new.replace(comm[1:-1], repl_string_start + comm[2:-1] + repl_string_end)
    # Putting newcommand definitions back
    for x in ph_repl:
        text_new = text_new.replace(x, ph_repl[x])
    return text_new


def file_string_repl(text, toc_entry):
    text_new = text
    repl_from_to = toc_entry['repl_source_from_to']
    repl_targets = toc_entry['repl_targets']
    for i, from_to in enumerate(repl_from_to):
        if from_to[0] in text_new:
            extract = extract_content(text_new, from_to[0], from_to[1])[0]
            for elem in extract:
                text_new = text_new.replace(elem, repl_targets[i])
    return text_new


def replace_newcommand(text, commands):
    text_new = text
    comms_list = commands['all_comms_to_replace']
    newcomm_indices = findall(text_new, newcommand)
    for ind in reversed(newcomm_indices):
        if ('{\\' + get_next_comm_string(text_new, ind + len(newcommand + '{'))[0] + '}') in comms_list:
            text_new = str_replace_from_index(text_new, newcommand, '\\textcolor', ind)
    return text_new


def preproc(toc_entry):
    source_file_path = source_root_dir + toc_entry["path"]
    # Just to ensure that path has / as the dir separator
    source_file_path = source_file_path.replace('\\', dir_sep)
    source_filename = source_file_path.split('/')[-1]
    source_filename_noext = source_filename[0:-4]
    # Creating the temporary directory for storing the preprocessed tex files.
    dirpath_part_after_tex_files = source_file_path.split(tex_files_dirname)[-1].replace(source_filename, '')
    tmp_current_dir = tmp_root_dir + dirpath_part_after_tex_files
    check_create_folder(tmp_current_dir)
    # Just copying the file to a tmp directory.
    tmp_tex_filepath = tmp_current_dir + source_filename_noext + '.tex'
    shutil.copy(source_file_path, tmp_tex_filepath)
    # Start preprocessing
    with open(tmp_tex_filepath, 'r', encoding='utf-8') as file:
        file_lines = file.readlines()
    # command_list_in_cur_file = helper_get_list_of_commands(file_lines).most_common()
    # Remove commented lines and empty commands (for example, else{}\fi{})
    # The replacement HACK. Works on source tex lines before any other function.
    replacement_hack_source_target = [['\\else{} \\fi{}', '\\fi']]
    for i, line in enumerate(file_lines):
        for replacement_hack in replacement_hack_source_target:
            file_lines[i] = file_lines[i].replace(replacement_hack[0], replacement_hack[1])
    cleaned_lines = clean_up_lines(file_lines)
    new_file_content = ''.join(cleaned_lines)
    # Add intro_text, if it exists in the current toc_entry
    if 'intro_text' in toc_entry:
        new_file_content = toc_entry['intro_text'] + '\n\n' + new_file_content
    # Do global from-to replacements
    new_file_content = file_string_repl(new_file_content, global_repl_from_to)
    # Do file-specific string replacement (repl_source_start, repl_source_end)
    if 'repl_source_from_to' in toc_entry:
        new_file_content = file_string_repl(new_file_content, toc_entry)
    # Adding {} to \else where \else does not end with either {} or \ifx
    new_file_content = add_brackets_to_else_without_ifx(new_file_content)
    # Getting the original '\\ifx', '\\fi' parts, and creating the replacement strings for them
    parts_original, parts_new = extract_content(new_file_content, '\\ifx', '\\fi', do_process_else=True)
    for i, part in enumerate(parts_new):
        current_part = process_else_ifx(part)
        current_part = replace_ifx_with_textcolor(current_part, '\\ifx', '\\fi', '\\textcolor')
        parts_new[i] = current_part
        new_file_content = new_file_content.replace(parts_original[i], parts_new[i])
    # Processing references (ref)
    new_file_content = change_command_value(new_file_content, '\\ref', 'TEXREFSTART', 'TEXREFEND',
                                            escape_underscore=True)[0]
    # Adding a prefix to label values to simplify post-processing
    new_file_content = change_command_value(new_file_content, '\\label', '{TEXLABEL', '}', escape_underscore=False)[0]
    # Removing \raisebox
    new_file_content = change_command_value(new_file_content, '\\raisebox', '', '', escape_underscore=False, ind_part_in_brackets=1, replace_comm_def_with_value=True)[0]
    # Preprocessing \unit ([] -> {})
    new_file_content = process_unit_comm(new_file_content)
    # REPLACEMENTS go here
    new_file_content = pre_replacements(new_file_content)
    # Replacing newcommand definitions with text placeholders
    new_file_content = macros_to_plaintext(new_file_content, comms_to_replace_all)
    # TODO replace newcommand with textcolor only if the command is in to replace
    new_file_content = replace_newcommand(new_file_content, comms_to_replace_all)
    # The string manipulation ends here.

    # The pandoc process
    run_path_as_list = []
    pandoc_log_filename = pandoc_logs_dir + dir_sep + dirpath_part_after_tex_files.replace('/',
                                                                                           '_') + source_filename_noext + '.log'
    tmp_htm_filepath = tmp_tex_filepath[:-4] + '.htm'
    run_path_as_list.extend([pandoc_path, tmp_tex_filepath, '-o', tmp_htm_filepath, '--log=' + pandoc_log_filename])
    pandoc_process = subprocess.run(run_path_as_list)
    # The beginning of the post-processing part
    with open(tmp_htm_filepath, 'r', encoding='utf-8') as file_htm:
        source_htm = file_htm.read()
    xml_root = xml_create_root(source_htm)
    xml_root = post_process_root(xml_root)
    target_topic_path = flare_dir_content + dirpath_part_after_tex_files
    target_topic_path = target_topic_path.replace('//', '/')
    check_create_folder(target_topic_path)
    target_topic_filepath = target_topic_path + source_filename_noext + '.htm'
    write_root(xml_root, target_topic_filepath)
    # Creating a Flare TOC entry
    if not ('type' in toc_entry and toc_entry['type'] == 'preamble'):
        global current_toc_parent_elem
        toc_entry_link_path = '/' + target_topic_filepath.replace(flare_root_dir, '')
        if 'toc_attribs' in toc_entry:
            extra_attribs = toc_entry['toc_attribs']
        else:
            extra_attribs = {}
        new_toc_entry = add_topic_to_toc(current_toc_parent_elem, toc_entry_link_path, extra_attribs)
        if 'children' in toc_entry and toc_entry['children'] is not None:
            previous_toc_parent_elem = current_toc_parent_elem
            current_toc_parent_elem = new_toc_entry
            for item in toc_entry['children']:
                preproc(item)
            current_toc_parent_elem = previous_toc_parent_elem
    logging.info('Preprocessing done on: ' + tmp_tex_filepath)


def create_toc_root(root_toc_attributes={'Version': '1'}):
    flare_toc_root = etree.Element("CatapultToc", attrib=root_toc_attributes)
    return flare_toc_root


def add_topic_to_toc(parent, topic_link, extra_attrib={}):
    toc_entry_attributes = {'Title': '[%=System.LinkedTitle%]', 'Link': topic_link}
    toc_entry_attributes.update(extra_attrib)
    new_toc_entry = etree.SubElement(parent, 'TocEntry', attrib=toc_entry_attributes)
    return new_toc_entry


def xml_create_root(xml_without_root):
    xml_from_string = etree.fromstring('<body>\n' + xml_without_root + '</body>', parser=parser_xml)
    root = etree.Element("html", nsmap=madcap_nsmap)
    root.text = '\n'
    etree.SubElement(root, "head").tail = '\n'
    root.append(xml_from_string)
    return root


def post_convert_text_to_elem(element, string_start, string_end, new_elem_tag, new_attribute_name):
    new_elems = []
    if (element.text is not None) and (string_start in element.text):
        split = element.text.split(string_start)
        element.text = split[0]
        del split[0]
        ind = 0
        for text_part in split:
            end_split = text_part.split(string_end)
            attributes = {new_attribute_name: end_split[0]}
            xref_elem = etree.Element(new_elem_tag, attrib=attributes)
            xref_elem.tail = end_split[1]
            element.insert(ind, xref_elem)
            ind += 1
            new_elems.append(xref_elem)
    # Processing the tail
    if (element.tail is not None) and (string_start in element.tail):
        split = element.tail.split(string_start)
        element.tail = split[0]
        del split[0]
        for text_part in split:
            end_split = text_part.split(string_end)
            attributes = {new_attribute_name: end_split[0]}
            xref_elem = etree.Element(new_elem_tag, attrib=attributes)
            xref_elem.tail = end_split[1]
            ind_elem = element.getparent().index(element)
            element.getparent().insert(ind_elem + 1, xref_elem)
            new_elems.append(xref_elem)
    return new_elems


# Post-processing functions start
def post_process_ref(element):
    all_elements = list(element.iter())
    for elem in all_elements:
        # Processing references (\ref)
        texref_start = 'TEXREFSTART'
        texref_end = 'TEXREFEND'
        post_convert_text_to_elem(elem, texref_start, texref_end, mc_xref_tag, 'href')


def append_or_create_attrib(element, attrib_name, string, delimiter=',', style_from_parent=False):
    # This condition is to handle \else{} where children have conditions of the same type (sounds confusing, but that's just for me to remember)
    delim_split = string.split(delimiter)
    for part in delim_split:
        if not (element.attrib.has_key('style')
                and element.attrib['style'].replace('color: IFXCOND_', '').startswith(part.split('_SEP_')[0])
                and style_from_parent):
            if element.attrib.has_key(attrib_name):
                element.attrib[attrib_name] += delimiter + part
            else:
                element.attrib[attrib_name] = part


def string_is_none_or_empty(string, do_strip=False):
    if string is None:
        is_none_or_empty = True
    else:
        if do_strip:
            string = string.strip()
        string = string.replace('\ufeff', '')
        if string == '':
            is_none_or_empty = True
        else:
            is_none_or_empty = False
    return is_none_or_empty


def element_has_text_or_child_tail(element):
    text_or_tail = True
    if len(element) > 0:
        if string_is_none_or_empty(element.text, do_strip=True) and string_is_none_or_empty(element[-1].tail, do_strip=True) and (element[-1].tag != 'br'):
            text_or_tail = False
        else:
            text_or_tail = True
    else:
        if element.text is not None:
            if string_is_none_or_empty(element.text.strip()):
                text_or_tail = False
            else:
                text_or_tail = True
        else:
            text_or_tail = False
    return text_or_tail


def img_in_span_strip(element):
    if len(element) == 1:
        if element.tag == 'span' and element[0].tag == 'img':
            if element.text is not None:
                element.text = element.text.strip()
            if element[0].tail is not None:
                element[0].tail = element[0].tail.strip()


# Processes divs and spans that pandoc created from \textcolor (ex \ifx)
def post_process_div_span_cond(element):
    ifxcond_string = 'color: IFXCOND_'
    divs_with_cond = element.xpath("//div[contains(@style, '" + ifxcond_string + "')]")
    for div in divs_with_cond:
        mc_cond = div.attrib['style'].replace(ifxcond_string, '', 1).lstrip()
        if div.attrib.has_key(mc_cond_attrib_name):
            mc_cond = div.attrib[mc_cond_attrib_name] + ',' + mc_cond
        if len(div) < 4:
            for child in div.getchildren():
                append_or_create_attrib(child, mc_cond_attrib_name, mc_cond, style_from_parent=True)
            div.tag = temp_tag_to_strip
        else:
            append_or_create_attrib(div, mc_cond_attrib_name, mc_cond, style_from_parent=False)
            del div.attrib['style']
    spans_with_cond = element.xpath("//span[contains(@style, '" + ifxcond_string + "')]")
    for span in spans_with_cond:
        # Stripping extra whitespace that pandoc inserts
        img_in_span_strip(span)
        mc_cond = span.attrib['style'].replace(ifxcond_string, '', 1).lstrip()
        if span.attrib.has_key(mc_cond_attrib_name):
            mc_cond = span.attrib[mc_cond_attrib_name] + ',' + mc_cond
        # TODO: What if there's text inside
        if (0 < len(span) < 4) and not element_has_text_or_child_tail(span):
            for child in span.getchildren():
                append_or_create_attrib(child, mc_cond_attrib_name, mc_cond, style_from_parent=True)
            span.tag = temp_tag_to_strip
        else:
            append_or_create_attrib(span, mc_cond_attrib_name, mc_cond, style_from_parent=False)
            del span.attrib['style']
    etree.strip_tags(element, temp_tag_to_strip)


# Turns the span generated from \caption into p with the caption class.
def post_captionclass(element):
    caption_spans = element.xpath("//*[contains(@style, '" + mc_image_caption_class + "')]")
    for elem in caption_spans:
        caption_class = elem.attrib['style'].replace('color: ', '')
        if elem.tag == 'span':
            if elem.getparent().tag == 'p':
                elem.tag = 'p'
                elem.attrib['class'] = caption_class
                del elem.attrib['style']
                elem.getparent().addnext(elem)
            else:
                print('WARNING: The parent of a span with the captionclass attribute is not p. Look into this. ' + etree.tostring(element))
        else:
            print('WARNING: The captionclass attribute is on a non-span element. Look into this. ' + etree.tostring(element))


def post_mc_keyword(element):
    keyword_elems = element.xpath("//*[contains(@style, '" + mc_keyword_textcolor_value + "')]")
    for elem in keyword_elems:
        elem.tag = mc_keyword_tag
        elem.attrib['term'] = elem.text
        elem.text = None
        del elem.attrib['style']


# This function moves the conditions from, for example, span to p, and then strips the span
def post_move_cond_to_parent(element):
    spans_with_cond = element.xpath('//span[@MadCap:conditions]', namespaces={'MadCap':madcap_namespace})
    for elem in spans_with_cond:
        if (elem.getparent().tag == 'p') and (len(elem.getparent()) == 1):
            if string_is_none_or_empty(elem.getparent().text, do_strip=True) and string_is_none_or_empty(elem.tail, do_strip=True):
                if len(elem.getparent().attrib) > 0:
                    print('WARNING: Parent p has attributes. Look into this: ' + etree.tostring(elem.getparent()).decode())
                    logging.warning('WARNING: Parent p has attributes. Look into this: ' + etree.tostring(elem.getparent()).decode())
                    input()
                else:
                    elem.getparent().attrib.update(elem.attrib)
                    elem.tag = temp_tag_to_strip
    etree.strip_tags(element, temp_tag_to_strip)


def post_process_root(xml_root):
    head_elem = xml_root.find('head')
    body_elem = xml_root.find('body')
    post_process_ref(body_elem)
    # post_strip_elems_with_cond(body_elem)
    post_process_div_span_cond(body_elem)
    post_captionclass(body_elem)
    post_msgclass(body_elem)
    post_mc_keyword(body_elem)
    return xml_root
# For more postprocessing, see the huge loop below (search for comment Various postprocessing)


def write_root(root, filename):
    indent_xml(root)
    result_str = etree.tostring(root, encoding="UTF-8")
    xml_declaration = b"<?xml version=\"1.0\" encoding=\"utf-8\"?>\n"
    result_str = xml_declaration + result_str
    output_file = open(filename, "wb")
    output_file.write(result_str)
    output_file.close()


def create_combined_newcomm_list(toc_entry_list):
    comms_to_replace_all = {'all_comms_to_replace': set()}
    for entry in toc_entry_list:
        json_path = tmp_root_dir + dir_sep + entry['path'][:-4] + '.json'
        with open(json_path, encoding="utf-8") as file:
            comm_data = json.load(file)
        for entry2 in comm_data['commands_to_replace']:
            # if entry2 in comms_to_replace_all:
            #     print('Entry already in combined list. ' + entry['path'][:-4] + ' ' + entry2)
            comms_to_replace_all['all_comms_to_replace'].add(entry2)
        # print('Preprocessing: reading commands from: ' + json_path)
    comms_to_replace_all['all_comms_to_replace'] = sorted(list(comms_to_replace_all['all_comms_to_replace']))
    with open('./newcomm/comms_to_replace_all.json', 'w', encoding='utf-8') as file:
        json.dump(comms_to_replace_all, file, indent=4)
    return comms_to_replace_all


def create_snippet_root():
    root = etree.Element("html", nsmap=madcap_nsmap)
    root.text = '\n'
    etree.SubElement(root, "head").tail = '\n'
    etree.SubElement(root, "body")
    return root


new_newcomm_elements = {}


def generate_snip_and_var(toc_entry):
    source_file_path = flare_dir_content + toc_entry["path"]
    # Just to ensure that path has / as the dir separator
    source_file_path = source_file_path.replace('\\', dir_sep)[0:-4] + '.htm'
    source_filename = source_file_path.split('/')[-1]
    check_create_folder(flare_dir_snippets_tex)
    root_tree = etree.parse(source_file_path, parser=parser_xml)
    root_element = root_tree.getroot()
    newcomm_elems = root_element.xpath("//*[contains(@style, 'color: \\')]")
    # Adding combined conditions on each newcomm element
    for elem in newcomm_elems:
        # Getting all conditions for the element
        if elem.attrib.has_key(mc_cond_attrib_name):
            elem_conditions = [elem.attrib[mc_cond_attrib_name]]
        else:
            elem_conditions = []
        current_parent = elem.getparent()
        while current_parent.tag != 'html':
            if current_parent.attrib.has_key(mc_cond_attrib_name):
                elem_conditions.append(current_parent.attrib[mc_cond_attrib_name])
            current_parent = current_parent.getparent()
        if len(elem_conditions) > 0:
            elem.attrib[mc_cond_attrib_name] = ','.join(elem_conditions)
    # Writing the file with conditions applied
    file_path_with_cond = source_file_path[:-4] + '_with_cond.htm'
    write_root(root_element, file_path_with_cond)
    # Writing the snippets (and variables)
    check_create_folder(flare_dir_snippets_tex)
    for elem in newcomm_elems:
        current_elem = copy.deepcopy(elem)
        if 'conditions' in toc_entry:
            append_or_create_attrib(current_elem, mc_cond_attrib_name, toc_entry['conditions'])
        current_newcomm_name = elem.attrib['style'].replace('color: \\', '').lower()
        item_filename = flare_dir_snippets_tex + current_newcomm_name + '.flsnp'
        del current_elem.attrib['style']
        if current_newcomm_name in new_newcomm_elements:
            new_newcomm_elements[current_newcomm_name].find('body').append(current_elem)
        else:
            snip_root = create_snippet_root()
            new_newcomm_elements[current_newcomm_name] = snip_root
            snip_body = snip_root.find('body')
            snip_body.append(current_elem)
        write_root(new_newcomm_elements[current_newcomm_name], item_filename)
    os.remove(source_file_path)
    os.remove(file_path_with_cond)


def tag_is_heading(tag_name):
    if tag_name.startswith('h') and len(tag_name) == 2:
        return True
    else:
        return False


def post_process_1(element):
    anchors = []
    references = []
    for elem in element.iter():
        if elem.attrib.has_key('id') and elem.attrib['id'].startswith(texlabel):
            anchors.append([elem.attrib['id'].replace(texlabel, ''), elem])
        # Special case for class="docpart"
        if elem.attrib.has_key('class') and elem.attrib['class'] == 'docpart':
            a_in_docpart = elem.find('a')
            elem.attrib['id'] = a_in_docpart.attrib['name']
            anchors.append([elem.attrib['id'].replace(texlabel, ''), elem])
        if elem.tag == mc_xref_tag:
            references.append([elem.attrib['href'], elem])
        if tag_is_heading(elem.tag):
            if elem.text is not None and elem.attrib.has_key('id'):
                if ''.join(filter(str.isalnum, elem.text)).lower() == ''.join(filter(str.isalnum, elem.attrib['id'])).lower():
                    del elem.attrib['id']
    # Processing anchors
    for anchor_item in anchors:
        elem = anchor_item[1]
        if elem.tag == 'span':
            elem.tag = 'a'
            elem.text = None
            # Stripping the whitespace from pandoc
            if elem.tail is not None:
                elem.tail = elem.tail.lstrip()
            del elem.attrib['label']
            elem.attrib['name'] = elem.attrib['id'].replace(texlabel, '')
            del elem.attrib['id']
            a_parent = elem.getparent()
            elem_copy = copy.deepcopy(elem)
            elem_copy.tail = None
            if elem.attrib['name'].startswith('fig:'):
                if a_parent.getnext().attrib.has_key('class') and a_parent.getnext().attrib['class'] == mc_image_caption_class:
                    # TODO: deepcopy
                    a_parent.getnext().append(elem_copy)
                    elem.tag = temp_tag_to_strip
                elif a_parent.getprevious().attrib.has_key('class') and a_parent.getprevious().attrib['class'] == mc_image_caption_class:
                    a_parent.getprevious().append(elem_copy)
                    elem.tag = temp_tag_to_strip
                else:
                    print('INFO: Could not find the image caption element, leaving the a tag where it is: ' + etree.tostring(elem).decode() + ' File path: ' + current_filepath)
                    logging.info('INFO: Could not find the image caption element, leaving the a tag where it is: ' + etree.tostring(elem).decode() + ' File path: ' + current_filepath)
            elif a_parent.getprevious() is not None:
                if tag_is_heading(a_parent.getprevious().tag):
                    a_parent.getprevious().append(elem_copy)
                    elem.tag = temp_tag_to_strip
                    if a_parent.getprevious().getprevious() is not None and tag_is_heading(a_parent.getprevious().getprevious().tag):
                        a_parent.getprevious().getprevious().append(copy.deepcopy(elem_copy))
        elif tag_is_heading(elem.tag):
            attributes = {'name': elem.attrib['id'].replace(texlabel, '')}
            # A special case for class="docpart", which must already have the a element
            if not (elem.attrib.has_key('class') and elem.attrib['class'] == "docpart"):
                a_elem = etree.SubElement(elem, 'a', attrib=attributes)
            del elem.attrib['id']
        else:
            print('WARNING. TEXLABEL neither on a span nor on h: ' + etree.tostring(elem).decode())
            input()
    etree.strip_tags(element, temp_tag_to_strip)
    for i, elem in enumerate(anchors):
        anchors[i] = elem[0]
    for i, elem in enumerate(references):
        references[i] = elem[0]
    return {'anchors': anchors, 'references': references}

# NOTE: Ensure that you process captions after removing the empty p
def post_strip_empty_elems(element):
    for elem in list(element.iter()):
        if (elem.tag == 'p') and (len(elem) == 0) and string_is_none_or_empty(elem.text, do_strip=True) and string_is_none_or_empty(elem.tail, do_strip=True):
            elem.getparent().remove(elem)


# START Graphics items config generation
graphic_items = helper2(source_root_dir)
graphic_items_config = dict({'graphic_items': graphic_items})

with open(config_file_graphics_items, 'w', encoding='utf-8') as file:
    json.dump(graphic_items_config, file, indent=4)

# END Graphics config generation

# Execution start
check_create_folder(pandoc_logs_dir)
# Processing the preamble entries from the config file and
# saving results (lists of commands) in json files.
for toc_entry in json_data['preamble']:
    extract_newcomm_defs(toc_entry)
# Reading preamble json files and creating a combined list of commands to replace.
comms_to_replace_all = create_combined_newcomm_list(json_data['preamble'])
for toc_entry in json_data['preamble']:
    preproc(toc_entry)
# Generate flare items from \newcommand definitions
for toc_entry in json_data['preamble']:
    generate_snip_and_var(toc_entry)

# Processing of the content of the User Manual starts here
# toc_parts are the Preface part, the HW part, and the SW part.

# Various postprocessing
# * Replacing condition values with values from the Flare project
# * Processing img elements
# * Adding values to glob_anchors, glob_refs
glob_anchors = []
glob_refs = []
for root_dir, dirs, files in os.walk(flare_dir_content):
    root_dir = root_dir.replace(os.path.sep, dir_sep)
    for filename in files:
        if filename.endswith(('.htm', '.flsnp')):
            current_filepath = root_dir + dir_sep + filename
            root_tree = etree.parse(current_filepath, parser=parser_xml)
            root_element = root_tree.getroot()
            # Replacing the TEXCOMM strings with variable/snippet elements
            if repl_string_start in etree.tostring(root_element, encoding='utf-8').decode():
                for elem in root_element.iter():
                    new_elements = post_convert_text_to_elem(elem, repl_string_start, repl_string_end, mc_snippet_block_tag, 'src')
                    for new_elem in new_elements:
                        # TODO: Check is target file exists
                        rel_path = os.path.relpath(flare_dir_snippets_tex, root_dir).replace('\\', dir_sep)
                        new_elem.attrib['src'] = rel_path + dir_sep + new_elem.attrib['src'].lower() + '.flsnp'
            # Replacing the condition placeholders with the Flare conditions
            if 'MadCap:conditions' in etree.tostring(root_element, encoding='utf-8').decode():
                for elem in root_element.iter():
                    if elem.attrib.has_key(mc_cond_attrib_name):
                        cond_raw = elem.attrib[mc_cond_attrib_name]
                        split1 = cond_raw.split(',')
                        final_conds = []
                        for cond_part in split1:
                            split_cond_part = cond_part.split('_SEP_')
                            split_cond_part[0] = flare_cond_map[split_cond_part[0]]
                            or_split = split_cond_part[1].split('_MYOR_')
                            for myor in or_split:
                                final_conds.append(split_cond_part[0] + '.' + flare_cond_map[myor])
                        elem.attrib[mc_cond_attrib_name] = ','.join(final_conds)
            # Doing extra processing (ref, label, and more)
            post_move_cond_to_parent(root_element)
            anch_ref = post_process_1(root_element)
            post_strip_empty_elems(root_element)
            # Extracting anchors (labels) and references
            for anch in anch_ref['anchors']:
                glob_anchors.append([anch, current_filepath])
            for ref in anch_ref['references']:
                glob_refs.append([ref, current_filepath])
            # Processing image paths. Just for me to search: graphics, figure.
            # Also deleting unnecessary attributes.
            # Before processing, changing all embed tags to img tags.
            embed_elems = root_element.xpath('//embed')
            for embed_elem in embed_elems:
                embed_elem.tag = 'img'
            img_elems = root_element.xpath('//img')
            for img_elem in img_elems:
                if img_elem.attrib.has_key('alt'):
                    del img_elem.attrib['alt']
                # Processing the src attribute. Putting the correct path to an image.
                # And getting the class attribute using the size map json file and the graphics items json file.
                current_src = img_elem.attrib['src']
                current_tex_filepath = current_filepath.replace(flare_dir_content, '')
                index_of_dot = current_tex_filepath.rfind('.')
                current_tex_filepath = current_tex_filepath[0:index_of_dot] + '.tex'
                # Handling '.htm' and '.flsnp' separately, because flsnp are new files generated from \newcommand definitions
                if current_filepath.endswith('.flsnp'):
                    for key, value in graphic_items.items():
                        if current_src in value:
                            style_from_tex = value[current_src]
                else:
                    if current_tex_filepath not in graphic_items:
                        logging.error('ERROR: the tex file path is not in the graphic items dict: ' + current_tex_filepath)
                    else:
                        if current_src not in graphic_items[current_tex_filepath]:
                            logging.error('ERROR: the image src not in graphic items dict: ' + current_src)
                        else:
                            style_from_tex = graphic_items[current_tex_filepath][current_src]
                # Processing case when style_from_tex is None (so that it matches the 'null' key in the image map)
                if style_from_tex is None:
                    style_from_tex = 'null'
                flare_img_class = graphics_size_map['graphic_size_map'][style_from_tex]['flare_class']
                if img_elem.attrib.has_key('class'):
                    logging.error('ERROR: the img element has the class attrib already: ' + current_filepath + ', ' + current_src)
                else:
                    img_elem.attrib['class'] = flare_img_class
                    # Deleting the style attrib after adding the class
                    if img_elem.attrib.has_key('style'):
                        del img_elem.attrib['style']
                # Processing the src path (adding extension)
                tex_img_full_path = source_root_dir + current_src
                if any(current_src.endswith(extension) for extension in tex_graphics_extensions_priority):
                    path_with_extension = tex_img_full_path
                    target_path = path_with_extension.replace(source_root_dir, flare_graphics_from_tex_dir)
                    pathlib.Path(os.path.dirname(target_path)).mkdir(parents=True, exist_ok=True)
                    shutil.copy(path_with_extension, target_path)
                    img_rel_path = os.path.relpath(os.path.dirname(target_path),
                                                   os.path.dirname(current_filepath)).replace('\\', dir_sep)
                    img_elem.attrib['src'] = img_rel_path + '/' + os.path.basename(target_path)
                    pdf_extensions = ('.pdf', '.PDF')
                    if target_path.endswith(pdf_extensions):
                        img_elem.attrib['src'] = img_elem.attrib['src'] + '#1'
                else:
                    # This loop is for the case when the graphic path does not have an extension in tex
                    for extension in tex_graphics_extensions_priority:
                        path_with_extension = tex_img_full_path + extension
                        target_path = path_with_extension.replace(source_root_dir, flare_graphics_from_tex_dir)
                        pathlib.Path(os.path.dirname(target_path)).mkdir(parents=True, exist_ok=True)
                        try:
                            shutil.copy(path_with_extension, target_path)
                            img_rel_path = os.path.relpath(os.path.dirname(target_path), os.path.dirname(current_filepath)).replace('\\', dir_sep)
                            img_elem.attrib['src'] = img_rel_path + '/' + os.path.basename(target_path)
                            pdf_extensions = ('.pdf', '.PDF')
                            if target_path.endswith(pdf_extensions):
                                img_elem.attrib['src'] = img_elem.attrib['src'] + '#1'
                            break
                        except:
                            continue
            # Fixing the issue with conditions: In Flare, if a least one condition on an element is included
            # in the target settings, the element is included even if other conditions on the same element are
            # excluded on the target.
            for elem in list(root_element.iter()):
                if mc_cond_attrib_name in elem.attrib and flare_cond_map['productNumber'] in elem.attrib[mc_cond_attrib_name]\
                        and flare_cond_map['productType'] in elem.attrib[mc_cond_attrib_name]:
                    series_cond = elem.attrib[mc_cond_attrib_name].split(',')[0]
                    other_cond = elem.attrib[mc_cond_attrib_name].split(',')
                    other_cond.remove(series_cond)
                    other_cond = ','.join(other_cond)
                    if element_has_text_or_child_tail(elem):
                        if len(elem) == 0:
                            etree.SubElement(elem, "span", {mc_cond_attrib_name: other_cond}).text = elem.text
                            elem.text = None
                            elem.attrib[mc_cond_attrib_name] = series_cond
                        else:
                            copy_of_elem = copy.deepcopy(elem)
                            copy_of_elem.tag = 'span'
                            copy_of_elem.attrib[mc_cond_attrib_name] = other_cond
                            elem.text = None
                            for child_to_remove in list(elem.getchildren()):
                                elem.remove(child_to_remove)
                            elem.append(copy_of_elem)
                            elem.attrib[mc_cond_attrib_name] = series_cond
                    else:
                        for child in elem:
                            append_or_create_attrib(child, mc_cond_attrib_name, other_cond)
                        elem.attrib[mc_cond_attrib_name] = series_cond
            # Deleting unnecessary br tags
            br_elems = root_element.xpath('//br')
            for elem in br_elems:
                if string_is_none_or_empty(elem.tail, do_strip=True):
                    if not (elem.getnext() is not None and elem.getnext().tag in inline_tags):
                        elem.getparent().remove(elem)
            # Unbinding code tags if they contain references
            code_elems = root_element.xpath('//code')
            for elem in code_elems:
                if elem.find(mc_xref_tag) is not None:
                    etree.strip_tags(elem.getparent(), 'code')
            # Stripping p from dd (otherwise alignment doesn't work)
            dd_elems = root_element.xpath('//dd')
            for elem in dd_elems:
                if elem.find('p') is not None:
                    etree.strip_tags(elem, 'p')
            # Changing h5 and h6 (that pandoc creates from \paragraph) to p.subtopic
            h5_elems = root_element.xpath("//h5")
            for elem in h5_elems:
                elem.tag = 'p'
                elem.attrib['class'] = mc_p_subtopic_class
            h6_elems = root_element.xpath("//h6")
            for elem in h6_elems:
                elem.tag = 'p'
                elem.attrib['class'] = mc_p_subtopic_class
            # Replacing the pinching hazard placeholder
            p_elems = root_element.xpath("//p")
            for elem in p_elems:
                if elem.text is not None and repl_pinching_hazard_placeholder in elem.text:
                    elem.tag = mc_snippet_block_tag
                    snippet_rel_path = os.path.relpath(os.path.dirname(flare_root_dir + repl_pinching_hazard_snippet_path),
                                               os.path.dirname(current_filepath)).replace('\\', dir_sep) + dir_sep \
                                       + os.path.basename(flare_root_dir + repl_pinching_hazard_snippet_path)
                    elem.attrib['src'] = snippet_rel_path
                    elem.text = None
            # Processing tables
            table_elems = root_element.xpath('//table')
            for table_elem in table_elems:
                table_elem.attrib['style'] = 'width: 100%'
                table_elem.attrib['class'] = 'my-table-1'
                thead = table_elem.find('thead')
                if thead is not None:
                    tr_in_thead = table_elem.find('thead').find('tr')
                    del tr_in_thead.attrib['class']
                # The following loop removes the "odd" class from td
                # for tr in table_elem.find('tbody').findall('tr'):
                #     if tr.attrib.has_key('class'):
                #         if tr.attrib['class'] == 'odd':
                #             del tr.attrib['class']
            # Removing class="unnumbered" from headings
            for elem in root_element.iter():
                if tag_is_heading(elem.tag):
                    if elem.attrib.has_key('class'):
                        if elem.attrib['class'] == 'unnumbered':
                            del elem.attrib['class']
            write_root(root_element, current_filepath)


print('Program finished.')
