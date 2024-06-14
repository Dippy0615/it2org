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
            "prev_note" : 0,
            "prev_note_index" : 0,   #index into the previous note played for this track in the org_data[channel]["notes"] list
            "rest" : False,
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
            for row in row_list:
                if len(row)>0:
                    for column in row:
                        if "instrument" in column.keys():
                            if tracks[column["channel"]]["instrument"] == -1:
                                tracks[column["channel"]]["instrument"] = column["instrument"]
                                org_data[column["channel"]]["instrument"] = column["instrument"]
                        if "volpan" in column.keys():
                            if column["volpan"] <= 64:
                                tracks[column["channel"]]["volume"] = column["volpan"]
                        if "note" in column.keys():
                            if column["note"] != 254 and column["note"] != 255:
                                #disable rest flag
                                tracks[column["channel"]]["rest"] = False
                                #add note and its data into notes list
                                org_data[column["channel"]]["notes"].append({
                                    "note" : column["note"]-24,
                                    "position" : tracks[column["channel"]]["position"],
                                    "volume" : tracks[column["channel"]]["volume"]*4-60,
                                    "pan" : 6
                                })
                                
                                #write duration for previous note
                                if tracks[column["channel"]]["prev_note"]>0:
                                    index = tracks[column["channel"]]["prev_note_index"]
                                    org_data[column["channel"]]["notes"][index]["duration"] = tracks[column["channel"]]["duration"] #the most readable line of code of all time
                                tracks[column["channel"]]["duration"] = 0

                                #update previous note info
                                tracks[column["channel"]]["prev_note"] = column["note"]
                                tracks[column["channel"]]["prev_note_index"] = len(org_data[column["channel"]]["notes"])-1
                                
                                org_data[column["channel"]]["total_notes"]+=1
                            else:
                                #enable rest flag
                                tracks[column["channel"]]["rest"] = True
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

module = impulsetracker.parse_file(MODULE, with_patterns=True, with_instruments=True)
write_org(module)