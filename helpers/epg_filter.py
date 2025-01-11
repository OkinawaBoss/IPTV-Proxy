import logging
import os
import re
import difflib
import unicodedata
import xml.etree.ElementTree as ET

from .utils import clean_text, normalize_name

def advanced_normalize(name):
    if not name:
        return ""
    name = unicodedata.normalize('NFD', name)
    name = name.encode('ascii', 'ignore').decode('ascii', 'ignore')
    name = name.lower().strip()
    # Remove punctuation or weird chars
    name = re.sub(r'[^a-z0-9\s]+', '', name)

    # Remove known suffixes/prefixes:
    common_terms = [" network", " tv", " hd", " uhd", " channel", " east", " west"]
    for term in common_terms:
        name = name.replace(term, "")

    return name.strip()


def filter_to_allowed_groups(input_path, output_path, allowed_groups):
    """
    In-place filter: only keep channels from allowed_groups.
    """
    if not os.path.exists(input_path):
        logging.error(f"[filter_to_allowed_groups] Input file not found: {input_path}")
        return

    logging.info(f"[filter_to_allowed_groups] Filtering to allowed groups in: {input_path}")
    try:
        with open(input_path, 'r', encoding='utf-8', errors='ignore') as file:
            content = file.read()

        filtered_lines = []
        keep_next_line = False

        for line in content.splitlines():
            if line.startswith("#EXTINF"):
                match = re.search(r'group-title="([^"]+)"', line)
                group_header = match.group(1) if match else None
                if group_header and group_header in allowed_groups:
                    filtered_lines.append(line)
                    keep_next_line = True
                else:
                    keep_next_line = False
            elif keep_next_line:
                filtered_lines.append(line)
                keep_next_line = False

        with open(output_path, 'w', encoding='utf-8') as out_file:
            out_file.write("\n".join(filtered_lines))

        logging.info(f"[filter_to_allowed_groups] Allowed-groups M3U saved to: {output_path}")
    except Exception as e:
        logging.error(f"[filter_to_allowed_groups] Failed to filter M3U file: {e}")



def clean_tvg_name(line):
    """
    Example: remove 'USA ' or special characters from tvg-name,
    but keep 'USA' if that's the *only* thing there.
    Also remove other special unicode like ᵁᴴᴰ.
    """
    match = re.search(r'tvg-name="([^"]+)"', line)
    if match:
        original_name = match.group(1).strip()
        # Force a normalized version of that name, but keep the display version if needed
        # We'll apply advanced normalization here just for safety.
        cleaned_name = advanced_normalize(original_name)
        # If original was exactly "USA" (case-insensitive), keep it as "USA"
        if cleaned_name == "usa" and original_name.upper() == "USA":
            # keep it as "USA"
            pass
        else:
            # put the cleaned version back in line
            line = line.replace(original_name, cleaned_name)
    return line


def load_epg_display_names(epg_path):
    """Load display-names => channel_id mapping from EPG."""
    display_name_to_id = {}
    try:
        tree = ET.parse(epg_path)
        root = tree.getroot()
        for channel in root.findall("channel"):
            disp_elem = channel.find("display-name")
            if disp_elem is not None and disp_elem.text:
                display_name = disp_elem.text.strip()
                channel_id = channel.get("id")
                if display_name and channel_id:
                    display_name_to_id[display_name] = channel_id
        logging.info("Loaded display names and IDs from EPG.")
    except Exception as e:
        logging.error(f"Failed to load EPG file: {e}")
    return display_name_to_id



def find_closest_display_name(tvg_name, display_name_to_id):
    """
    Use fuzzy matching to find the best channel ID for tvg_name.
    Return channel_id if best_score >= 0.8, else None.
    """
    if not tvg_name or not display_name_to_id:
        return None
    norm_tvg = advanced_normalize(tvg_name)
    best_match = None
    best_score = 0.0

    for disp_name, chan_id in display_name_to_id.items():
        norm_disp = advanced_normalize(disp_name)
        if not norm_disp:
            continue
        score = difflib.SequenceMatcher(None, norm_tvg, norm_disp).ratio()
        if score > best_score:
            best_match = disp_name
            best_score = score

    return display_name_to_id[best_match] if best_score >= 0.8 else None


def filter_m3u(input_path, output_path, epg_display_name_to_id, allowed_groups=None):
    """
    1) Do NOT rename the final tvg-name except remove "USA " at the beginning if it exists.
    2) For fuzzy matching, use advanced_normalize(tvg-name) internally, but keep original display name.
    3) Insert tvg-ID if matched.
    """
    from .epg_filter import find_closest_display_name  # or wherever find_closest_display_name is
    import logging
    import os
    import re

    if allowed_groups is None:
        # Keep all groups
        keep_all = True
        allowed_groups = []
    else:
        keep_all = False

    if not os.path.exists(input_path):
        logging.error(f"Input file not found: {input_path}")
        return

    logging.info(f"Filtering M3U file (assigning tvg-ID): {input_path}")
    try:
        with open(input_path, 'r', encoding='utf-8') as file:
            content = file.read()

        filtered = []
        add_next_line = False

        for line in content.splitlines():
            if line.startswith("#EXTINF"):
                match_group = re.search(r'group-title="([^"]+)"', line)
                group_name = match_group.group(1) if match_group else None

                # If keep_all == True, or group_name is in allowed_groups, we keep the channel
                if keep_all or (group_name and group_name in allowed_groups):
                    # Optional: remove leading "USA " from tvg-name
                    original_tvg_name_match = re.search(r'tvg-name="([^"]+)"', line)
                    if original_tvg_name_match:
                        original_tvg_name = original_tvg_name_match.group(1)
                        if original_tvg_name.startswith("USA "):
                            new_tvg_name = original_tvg_name.replace("USA ", "", 1)
                            line = line.replace(original_tvg_name, new_tvg_name)
                            # Fuzzy-match using new_tvg_name
                            matched_id = find_closest_display_name(new_tvg_name, epg_display_name_to_id)
                        else:
                            matched_id = find_closest_display_name(original_tvg_name, epg_display_name_to_id)

                        if matched_id:
                            # Insert or replace tvg-ID
                            if 'tvg-ID=' in line:
                                line = re.sub(r'tvg-ID="[^"]*"', f'tvg-ID="{matched_id}"', line)
                            else:
                                line = line.replace('tvg-name=', f'tvg-ID="{matched_id}" tvg-name=')

                    filtered.append(line)
                    add_next_line = True
                else:
                    add_next_line = False

            elif add_next_line:
                # This is the next line (usually the URL) for a kept channel
                filtered.append(line)
                add_next_line = False

        with open(output_path, 'w', encoding='utf-8') as out_file:
            out_file.write("\n".join(filtered))

        logging.info(f"Filtered playlist saved to: {output_path}")

    except Exception as e:
        logging.error(f"Failed to filter M3U file: {e}")



def filter_epg(input_path, output_path):
    """
    Filter EPG XML file based on |US| channels and clean the display names, etc.
    This part is fairly unchanged from your original code.
    """
    if not os.path.exists(input_path):
        logging.error(f"Input file not found: {input_path}")
        return

    logging.info(f"Filtering EPG file: {input_path}")
    try:
        tree = ET.parse(input_path)
        root = tree.getroot()
        allowed_channels = set()

        for channel in root.findall("channel"):
            display_name_element = channel.find("display-name")
            if display_name_element is not None:
                display_name = display_name_element.text if display_name_element.text else ""
                if display_name.startswith("|US|"):
                    cleaned_name = clean_text(display_name)
                    display_name_element.text = cleaned_name
                    allowed_channels.add(channel.get("id"))
                else:
                    root.remove(channel)

        for programme in root.findall("programme"):
            channel_id = programme.get("channel")
            if channel_id not in allowed_channels:
                root.remove(programme)

        tree.write(output_path, encoding="utf-8", xml_declaration=True)
        logging.info(f"Filtered EPG saved to: {output_path}")

    except Exception as e:
        logging.error(f"Failed to filter EPG file: {e}")
