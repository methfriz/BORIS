"""
BORIS
Behavioral Observation Research Interactive Software
Copyright 2012-2018 Olivier Friard

  This program is free software; you can redistribute it and/or modify
  it under the terms of the GNU General Public License as published by
  the Free Software Foundation; either version 2 of the License, or
  (at your option) any later version.

  This program is distributed in the hope that it will be useful,
  but WITHOUT ANY WARRANTY; without even the implied warranty of
  MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
  GNU General Public License for more details.

  You should have received a copy of the GNU General Public License
  along with this program; if not, write to the Free Software
  Foundation, Inc., 51 Franklin Street, Fifth Floor, Boston,
  MA 02110-1301, USA.
"""

from config import *
import logging
import os
import json
import utilities
from shutil import copyfile
from decimal import *


def extract_observed_subjects(pj, selected_observations):
    """
    extract unique subjects present in observations list
    
    return: list
    """

    observed_subjects = []

    # extract events from selected observations
    for events in [pj[OBSERVATIONS][x][EVENTS] for x in pj[OBSERVATIONS] if x in selected_observations]:
        for event in events:
            observed_subjects.append(event[EVENT_SUBJECT_FIELD_IDX])

    # remove duplicate
    return list(set(observed_subjects))



def open_project_json(projectFileName):
    """
    open project json
    
    Args:
        projectFileName (str): path of project
        
    Returns:
        str: project path
        bool: True if project changed
        dict: BORIS project
        str: message
    """

    logging.debug("open project: {0}".format(projectFileName))

    projectChanged = False
    msg = ""

    if not os.path.isfile(projectFileName):
        return projectFileName, projectChanged, {"error": "File {} not found".format(projectFileName)}, msg

    s = open(projectFileName, "r").read()

    try:
        pj = json.loads(s)
    except:
        return projectFileName, projectChanged, {"error": "This project file seems corrupted"}, msg


    # transform time to decimal
    pj = utilities.convert_time_to_decimal(pj)

    # add coding_map key to old project files
    if not "coding_map" in pj:
        pj["coding_map"] = {}
        projectChanged = True

    # add subject description
    if "project_format_version" in pj:
        for idx in [x for x in pj[SUBJECTS]]:
            if not "description" in pj[SUBJECTS][idx]:
                pj[SUBJECTS][idx]["description"] = ""
                projectChanged = True

    # check if project file version is newer than current BORIS project file version
    if "project_format_version" in pj and Decimal(pj["project_format_version"]) > Decimal(project_format_version):
      
        return projectFileName, projectChanged, {"error": ("This project file was created with a more recent version of BORIS.\n"
                                                 "You must update BORIS to open it")}, msg


    # check if old version  v. 0 *.obs
    if "project_format_version" not in pj:

        # convert VIDEO, AUDIO -> MEDIA
        pj['project_format_version'] = project_format_version
        projectChanged = True

        for obs in [x for x in pj[OBSERVATIONS]]:

            # remove 'replace audio' key
            if "replace audio" in pj[OBSERVATIONS][obs]:
                del pj[OBSERVATIONS][obs]['replace audio']

            if pj[OBSERVATIONS][obs][TYPE] in ['VIDEO', 'AUDIO']:
                pj[OBSERVATIONS][obs][TYPE] = MEDIA

            # convert old media list in new one
            if len(pj[OBSERVATIONS][obs][FILE]):
                d1 = {PLAYER1: [pj[OBSERVATIONS][obs][FILE][0]]}

            if len(pj[OBSERVATIONS][obs][FILE]) == 2:
                d1[PLAYER2] = [pj[OBSERVATIONS][obs][FILE][1]]

            pj[OBSERVATIONS][obs][FILE] = d1

        # convert VIDEO, AUDIO -> MEDIA
        for idx in [x for x in pj[SUBJECTS]]:
            key, name = pj[SUBJECTS][idx]
            pj[SUBJECTS][idx] = {"key": key, "name": name, "description": ""}
        
        msg = ("The project file was converted to the new format (v. {}) in use with your version of BORIS.<br>"
                                                    "Choose a new file name for saving it.").format(project_format_version)
        projectFileName = ""


    for obs in pj[OBSERVATIONS]:
        if not "time offset second player" in pj[OBSERVATIONS][obs]:
            pj[OBSERVATIONS][obs]["time offset second player"] = Decimal("0.0")
            projectChanged = True

    # update modifiers to JSON format

    project_lowerthan4 = False

    logging.debug("project_format_version: {}".format(utilities.versiontuple(pj["project_format_version"])))

    if "project_format_version" in pj and utilities.versiontuple(pj["project_format_version"]) < utilities.versiontuple("4.0"):

        for idx in pj[ETHOGRAM]:
            if pj[ETHOGRAM][idx]["modifiers"]:
                if isinstance(pj[ETHOGRAM][idx]["modifiers"], str):
                    project_lowerthan4 = True
                    modif_set_list = pj[ETHOGRAM][idx]["modifiers"].split("|")
                    modif_set_dict = {}
                    for modif_set in modif_set_list:
                        modif_set_dict[str(len(modif_set_dict))] = {"name": "", "type": SINGLE_SELECTION, "values": modif_set.split(",")}
                    pj[ETHOGRAM][idx]["modifiers"] = dict(modif_set_dict)
            else:
                pj[ETHOGRAM][idx]["modifiers"] = {}

        if not project_lowerthan4:
            msg = "The project version was updated from {} to {}".format(pj["project_format_version"], project_format_version)
            pj["project_format_version"] = project_format_version
            projectChanged = True


    # add category key if not found
    for idx in pj[ETHOGRAM]:
        if "category" not in pj[ETHOGRAM][idx]:
            pj[ETHOGRAM][idx]["category"] = ""

    logging.debug("project_lowerthan4: {}".format(project_lowerthan4))

    if project_lowerthan4:

        copyfile(projectFileName, projectFileName.replace(".boris", "_old_version.boris"))
        
        msg = ("The project was updated to the current project version ({project_format_version}).\n\n"
                                                    "The old file project was saved as {project_file_name}").format(project_format_version=project_format_version,
                                                                                                                     project_file_name=projectFileName.replace(".boris", "_old_version.boris"))


    # if one file is present in player #1 -> set "media_info" key with value of media_file_info
    project_updated = False

    for obs in pj[OBSERVATIONS]:
        if pj[OBSERVATIONS][obs][TYPE] in [MEDIA] and "media_info" not in pj[OBSERVATIONS][obs]:
            pj[OBSERVATIONS][obs]['media_info'] = {"length": {}, "fps": {}, "hasVideo": {}, "hasAudio": {}}
            for player in [PLAYER1, PLAYER2]:
                # fix bug Anne Maijer 2017-07-17
                if pj[OBSERVATIONS][obs]["file"] == []:
                    pj[OBSERVATIONS][obs]["file"] = {"1": [], "2": []}

                for media_file_path in pj[OBSERVATIONS][obs]["file"][player]:
                    # FIX: ffmpeg path
                    
                    ret, msg = utilities.check_ffmpeg_path()
                    if not ret:
                        return projectFileName, projectChanged, {"error": "FFmpeg path not found"}, ""
                    else:
                        ffmpeg_bin = msg
                    
                    nframe, videoTime, videoDuration, fps, hasVideo, hasAudio = utilities.accurate_media_analysis(ffmpeg_bin, media_file_path)

                    if videoDuration:
                        pj[OBSERVATIONS][obs]['media_info']["length"][media_file_path] = videoDuration
                        pj[OBSERVATIONS][obs]['media_info']["fps"][media_file_path] = fps
                        pj[OBSERVATIONS][obs]['media_info']["hasVideo"][media_file_path] = hasVideo
                        pj[OBSERVATIONS][obs]['media_info']["hasAudio"][media_file_path] = hasAudio
                        project_updated, projectChanged = True, True
                    else:  # file path not found
                        if ("media_file_info" in pj[OBSERVATIONS][obs]
                            and len(pj[OBSERVATIONS][obs]["media_file_info"]) == 1
                            and len(pj[OBSERVATIONS][obs]["file"][PLAYER1]) == 1
                            and len(pj[OBSERVATIONS][obs]["file"][PLAYER2]) == 0):
                                media_md5_key = list(pj[OBSERVATIONS][obs]["media_file_info"].keys())[0]
                                # duration
                                pj[OBSERVATIONS][obs]["media_info"] = {"length": {media_file_path:
                                         pj[OBSERVATIONS][obs]["media_file_info"][media_md5_key]["video_length"]/1000}}
                                project_updated, projectChanged = True, True

                                # FPS
                                if "nframe" in pj[OBSERVATIONS][obs]["media_file_info"][media_md5_key]:
                                    pj[OBSERVATIONS][obs]['media_info']['fps'] = {media_file_path:
                                         pj[OBSERVATIONS][obs]['media_file_info'][media_md5_key]['nframe']
                                         / (pj[OBSERVATIONS][obs]['media_file_info'][media_md5_key]['video_length']/1000)}
                                else:
                                    pj[OBSERVATIONS][obs]['media_info']['fps'] = {media_file_path: 0}


    if project_updated:
        msg = "The media files information was updated to the new project format."
        
    return projectFileName, projectChanged, pj, msg
    
    
def event_type(code, ethogram):
    """
    returns type of event for code
    """
    for idx in ethogram:
        if ethogram[idx]['code'] == code:
            return ethogram[idx][TYPE]
    return None

    
def check_state_events_obs(pj, obsId):
    """
    check state events
    check if number is odd
    
    Args:
        pj (dict): BORIS project
        obsId (str): id of observation to check
        
    Returns:
        set (bool, str): True/False, message
    """
    
    # check if behaviors are defined as "state event"
    event_types = {pj[ETHOGRAM][idx]["type"] for idx in pj[ETHOGRAM]}

    if not event_types or event_types == {"Point event"}:
        return (True, "No behavior is defined as `State event`")

    out = ""
    flagStateEvent = False
    subjects = [event[EVENT_SUBJECT_FIELD_IDX] for event in pj[OBSERVATIONS][obsId][EVENTS]]
    ethogram_behaviors = {pj[ETHOGRAM][idx]["code"] for idx in pj[ETHOGRAM]}

    for subject in sorted(set(subjects)):

        behaviors = [event[EVENT_BEHAVIOR_FIELD_IDX] for event in pj[OBSERVATIONS][obsId][EVENTS]
                     if event[EVENT_SUBJECT_FIELD_IDX] == subject]

        for behavior in sorted(set(behaviors)):
            if behavior not in ethogram_behaviors:
                return (False, "The behaviour <b>{}</b> not found in the ethogram.<br>".format(behavior))
            else:
                if STATE in event_type(behavior, pj[ETHOGRAM]).upper():
                    flagStateEvent = True
                    lst, memTime = [], {}
                    for event in [event for event in pj[OBSERVATIONS][obsId][EVENTS]
                                  if event[EVENT_BEHAVIOR_FIELD_IDX] == behavior and
                                  event[EVENT_SUBJECT_FIELD_IDX] == subject]:

                        behav_modif = [event[EVENT_BEHAVIOR_FIELD_IDX], event[EVENT_MODIFIER_FIELD_IDX]]

                        if behav_modif in lst:
                            lst.remove(behav_modif)
                            del memTime[str(behav_modif)]
                        else:
                            lst.append(behav_modif)
                            memTime[str(behav_modif)] = event[EVENT_TIME_FIELD_IDX]

                    for event in lst:
                        out += ("""The behavior <b>{behavior}</b> {modifier} is not PAIRED for subject"""
                                """ "<b>{subject}</b>" at <b>{time}</b><br>""").format(
                                      behavior=behavior,
                                      modifier=("(modifier "+ event[1] + ") ") if event[1] else "",
                                      subject=subject if subject else NO_FOCAL_SUBJECT,
                                      time=memTime[str(event)] if self.timeFormat == S else utilities.seconds2time(memTime[str(event)]))

    return (False, out) if out else (True, "All state events are PAIRED")
