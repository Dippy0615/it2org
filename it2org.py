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
    vol = int((volume/64) * 254)
    return max(int(0.8 * vol), 0)

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
                if tracks[channel]["duration"] <= 255:
                    org_data[channel]["notes"][index]["duration"] = tracks[channel]["duration"]
                else:
                    org_data[channel]["notes"][index]["duration"] = 255

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
            "no_change" : False,
            "no_change_list" : [],   #list of dicts that represet each no change event
        })

    sample_volumes = [-1] * 255 #sample volumes for each instrument used
    order_positions = [0] * len(module["orders"]) #orgayana positions for each order, used for the Bxx command.

    #actually populate org_data's dicts
    for order_id, order in enumerate(module["orders"]):
        if order == 254:
            pass
        elif order == 255:
            #end of song
            #write duration for notes
            for i in range(TRACK_NUM):
                if tracks[i]["prev_note"]>0:
                    index = tracks[i]["prev_note_index"]
                    if org_data[i]["notes"][index]["duration"]>255:
                        org_data[i]["notes"][index]["duration"] = 255
                    else:
                        org_data[i]["notes"][index]["duration"] = tracks[i]["duration"]
                    tracks[i]["duration"] = 0
            loop_end_position = tracks[0]["position"]
            break
        else:
            pattern = module["patterns"][order]
            row_list = pattern[0]
            order_positions[order_id] = tracks[0]["position"]
            for row_id, row in enumerate(row_list):
                if len(row)>0:
                    for column in row:
                        if "instrument" in column.keys():
                            if tracks[column["channel"]]["instrument"] == -1:
                                #try to map an IT instrument to an orgayana instrument
                                name = str(module["instruments"][column["instrument"]-1]["name"])
                                if "instrument:" in name:
                                    ins = int(name[13:len(name)-1])
                                    if column["channel"]>7: ins-=100
                                    tracks[column["channel"]]["instrument"] = ins
                                    org_data[column["channel"]]["instrument"] = ins
                                else:
                                #else, the first instrument used is set as the orgayana instrument
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
                            if effect[0] == "B":
                                order = int(effect[1:], 16)
                                loop_start_position = order_positions[order]
                            elif effect[0] == "D":
                                if not "note" in column.keys() and tracks[column["channel"]]["rest"] == False and tracks[column["channel"]]["prev_note"]>0:
                                    fade_in = int(effect[1], 16)
                                    fade_out = int(effect[2], 16)
                                    if fade_in==0: #fade out
                                        tracks[column["channel"]]["no_change"] = True
                                        tracks[column["channel"]]["volume"] -= org_get_volume(fade_out * (module["initspeed"]/4))
                                    elif fade_out==0: #fade in
                                        tracks[column["channel"]]["no_change"] = True
                                        tracks[column["channel"]]["volume"] += org_get_volume(fade_in * (module["initspeed"]/4))
                            elif effect[0] == "X":
                                #panning
                                pan = int(effect[1:], 16)
                                tracks[column["channel"]]["pan"] = pan
                                if not "note" in column.keys() and tracks[column["channel"]]["rest"] == False and tracks[column["channel"]]["prev_note"]>0:
                                    #enable 'no change' orgayana flag if tracker note is absent
                                    tracks[column["channel"]]["no_change"] = True
                        if "note" in column.keys():
                            if column["note"] != 254 and column["note"] != 255:
                                if not "volpan" in column.keys():
                                    #use sample volume if volume row is not present
                                    if sample_volumes[column["instrument"]]==-1:
                                        #get the sample from the instrument's sample map, and use that sample's volume
                                        table = list(module["instruments"][column["instrument"]-1]["smptable"])
                                        table_list = list(table)
                                        if len(table_list)>0:
                                            sample_num = table_list[column["note"]][0]-1
                                            volume = module["samples"][sample_num]["volume"]
                                            sample_volumes[column["instrument"]] = volume
                                            tracks[column["channel"]]["volume"] = volume
                                    else:
                                        tracks[column["channel"]]["volume"] = sample_volumes[column["instrument"]] 

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
                    if tracks[i]["rest"] == False and tracks[i]["duration"] < 255:
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