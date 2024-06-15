from sys import argv
from pytrax import impulsetracker

def validate_module(file):
    if file.read(4) != b"IMPM":
        print("ERROR: The file provided is not a valid .it module.")
        exit(0)    

if len(argv) == 3:
    MODULE = argv[1]
    ORG = argv[2]
    validate_module(open(MODULE, "rb"))
else:
    print("IT2ORG v1.0 by Dippy")
    print("Usage: it2org.py filename.it outfile.org")
    exit(0)

def org_get_volume(volume):
    vol = int((volume/64) * 254)-60
    return vol if vol > 0 else 0

def org_get_panning(panning):
    return int((panning/255) * 12)

def org_write_note(org_data, channel, note, tracks, no_change=False):
    if no_change==False:
        org_data[channel]["notes"].append({
                    "note" : note-24,
                    "position" : tracks[channel]["position"],
                    "volume" : org_get_volume(tracks[channel]["volume"]),
                    "pan" : org_get_panning(tracks[channel]["pan"]),
                    "duration" : 0, #will be set later
                    "no_change" : False
                })
        #write duration for previous note
        if tracks[channel]["prev_note"]>0:
            index = tracks[channel]["prev_note_index"]
            if org_data[channel]["notes"][index]["no_change"] == False:
                org_data[channel]["notes"][index]["duration"] = tracks[channel]["duration"]

            tracks[channel]["duration"] = 0
            tracks[channel]["prev_note_index"] = len(org_data[channel]["notes"])-1
    else:
        no_change_data = tracks[channel]["no_change_list"][0]
        org_data[channel]["notes"].append({
                    "note" : 255,
                    "position" : no_change_data["position"],
                    "volume" : org_get_volume(tracks[channel]["volume"]),
                    "pan" : org_get_panning(tracks[channel]["pan"]),
                    "duration" : 0, #duration is not relevant for no change events
                    "no_change" : True
                })
        tracks[channel]["no_change_list"].pop(0)
    
    tracks[channel]["prev_note"] = note
    org_data[channel]["total_notes"]+=1

def org_add_no_change_event(channel, tracks):
    tracks[channel]["no_change_list"].append({
                "position" : tracks[channel]["position"],
                "note" : tracks[channel]["prev_note"],
                "volume" : tracks[channel]["volume"],
                "pan" : tracks[channel]["pan"]
            })
    
def write_org(module):    
    wait = int(2500/module["inittempo"] * module["initspeed"])
    beats_per_measure = 4
    steps_per_beat = 4
    steps_per_measure = steps_per_beat * beats_per_measure
    loop_start_position = 0
    loop_end_position = 0
    current_measure = 0

    TRACK_NUM = 16
    
    #list of dicts that represent each orgayana track
    org_data = []
    for i in range(TRACK_NUM):
        org_data.append({
            "freq" : 1000,
            "instrument" : 0,   #0-99 for melody tracks (1-8), 0-11 for drum tracks (9-16)
            "pi" : False,
            "total_notes" : 0,
            "notes" : []    #list of dicts that represent each note and its properties
        })

    #list of dicts that represent each impulse tracker channel
    tracks = []
    for i in range(TRACK_NUM):
        tracks.append({
            "position" : 0,
            "duration" : 0,
            "instrument" : -1,
            "volume" : 64,
            "pan" : 128,
            "prev_note" : 0,
            "prev_note_index" : 0,   #index into the previous note played for this track in the org_data[channel]["notes"] list, excluding no change notes
            "rest" : False,
            "sample_volume" : -1,
            "no_change" : False,
            "no_change_list" : [],   #list of dicts that represet each no change event
        })
    
    #actually populate org_data's dicts
    for order in module["orders"]:
        if order == 254:
            pass
        elif order == 255:
            #end of song
            #write duration for notes
            for i in range(TRACK_NUM):
                if tracks[i]["prev_note"]>0:
                    index = tracks[i]["prev_note_index"]
                    org_data[i]["notes"][index]["duration"] = tracks[i]["duration"]
                    tracks[i]["duration"] = 0
            loop_end_position = tracks[0]["position"]
            break
        else:
            pattern = module["patterns"][order]
            row_list = pattern[0]
            for row_id, row in enumerate(row_list):
                if len(row)>0:
                    for column in row:
                        if "instrument" in column.keys():
                            #first instrument used is set as the orgayana instrument
                            if tracks[column["channel"]]["instrument"] == -1:
                                tracks[column["channel"]]["instrument"] = column["instrument"]
                                org_data[column["channel"]]["instrument"] = column["instrument"]-1
                                #drum sounds start at 0
                                if column["channel"]>7: org_data[column["channel"]]["instrument"]-=100
                        if "volpan" in column.keys():
                            if column["volpan"] <= 64:
                                tracks[column["channel"]]["volume"] = column["volpan"]
                                if not "note" in column.keys() and tracks[column["channel"]]["rest"] == False and tracks[column["channel"]]["prev_note"]>0:
                                    #enable 'no change' orgayana flag if tracker note is absent
                                    tracks[column["channel"]]["no_change"] = True
                        if "command" in column.keys():
                            effect = column["command"]
                            if effect[0] == "X":
                                #panning
                                pan = int(effect[1:], 16)
                                tracks[column["channel"]]["pan"] = pan
                            if not "note" in column.keys() and tracks[column["channel"]]["rest"] == False and tracks[column["channel"]]["prev_note"]>0:
                                    #enable 'no change' orgayana flag if tracker note is absent
                                    tracks[column["channel"]]["no_change"] = True
                        if "note" in column.keys():
                            if column["note"] != 254 and column["note"] != 255:
                                if not "volpan" in column.keys():
                                    tracks[column["channel"]]["volume"] = 64

                                #disable rest and no change flags
                                tracks[column["channel"]]["rest"] = False
                                tracks[column["channel"]]["no_change"] = False

                                #add note and its data into notes list
                                org_write_note(org_data, column["channel"], column["note"], tracks)
                            else:
                                #enable rest flag
                                tracks[column["channel"]]["rest"] = True
                        if tracks[column["channel"]]["no_change"] == True:
                            #add no change event to the list
                            org_add_no_change_event(column["channel"], tracks)
                            tracks[column["channel"]]["no_change"] = False
                            org_write_note(org_data, column["channel"], 255, tracks, True)
                for i in range(TRACK_NUM):
                    tracks[i]["position"]+=1
                    if tracks[i]["rest"] == False:
                        tracks[i]["duration"]+=1
                if tracks[0]["position"] % steps_per_measure == 0:
                    current_measure+=1
    
    #writing the org file
    org = open(ORG, "wb")
    #File Properties
    org.write(b"Org-02")
    org.write(wait.to_bytes(2, "little"))
    org.write(beats_per_measure.to_bytes(1))
    org.write(steps_per_beat.to_bytes(1))
    org.write(loop_start_position.to_bytes(4, "little"))
    org.write(loop_end_position.to_bytes(4, "little"))
    #Instruments
    for i in range(TRACK_NUM):
        data = org_data[i]
        org.write(data["freq"].to_bytes(2, "little"))
        org.write(data["instrument"].to_bytes(1))
        org.write(data["pi"].to_bytes(1))
        org.write(data["total_notes"].to_bytes(2, "little"))
    for i in range(TRACK_NUM):
    #Note Positions
        for note in org_data[i]["notes"]:
            org.write(note["position"].to_bytes(4, "little"))
    #Note Values
        for note in org_data[i]["notes"]:
            org.write(note["note"].to_bytes(1))
    #Note Durations
        for note in org_data[i]["notes"]:
            org.write(note["duration"].to_bytes(1))
    #Note Volumes
        for note in org_data[i]["notes"]:
            org.write(note["volume"].to_bytes(1))
    #Note Pannings
        for note in org_data[i]["notes"]:
            org.write(note["pan"].to_bytes(1))
    org.close()

module = impulsetracker.parse_file(MODULE, with_patterns=True, with_instruments=True, with_samples=True)
write_org(module)