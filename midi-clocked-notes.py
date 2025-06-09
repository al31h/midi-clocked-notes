import argparse
import configparser
import rtmidi
import time
import sys

MIDI_CLOCK = 0xF8
MIDI_START = 0xFA
MIDI_STOP = 0xFC

def list_ports(midi_class):
    return [midi_class.get_port_name(i) for i in range(midi_class.get_port_count())]

def find_port(midi_class, keyword):
    for i, name in enumerate(list_ports(midi_class)):
        if keyword and keyword.lower() in name.lower():
            return i, name
    return None, None

def parse_args_and_config():
    parser = argparse.ArgumentParser(description="Convert MIDI Clock/Start/Stop to Note On messages.")
    parser.add_argument("--in-port", help="Substring of MIDI input port name")
    parser.add_argument("--out-port", help="Substring of MIDI output port name")

    parser.add_argument("--midi-channel", type=int, default=15, help="MIDI Channel used to send notes (15 by default)")

    parser.add_argument("--beats-per-bar", type=int, default=4, help="Beats per bar (4 by default)")
    parser.add_argument("--ticks-per-beat", type=int, default=1, help="Ticks per beat (default 1 = quarter)")

    parser.add_argument("--note-bar-1", type=int, default=0, help="Note every bar")
    parser.add_argument("--note-bar-2", type=int, default=0, help="Note every 2 bars")
    parser.add_argument("--note-bar-4", type=int, default=0, help="Note every 4 bars")
    parser.add_argument("--note-bar-8", type=int, default=0, help="Note every 8 bars")
    parser.add_argument("--note-bar-16", type=int, default=0, help="Note every 16 bars")
    
    parser.add_argument("--note", type=int, default=60, help="The note to send is the option notes-per-bar is used")
    parser.add_argument("--notes-per-bar", type=int, default=4, help="Note every XX bars (default note C3 each 4 bars)")
    
    parser.add_argument("--note-start", type=int, default=30, help="Note on MIDI Start")
    parser.add_argument("--note-stop", type=int, default=31, help="Note on MIDI Stop")

    parser.add_argument("--show-bpm", action="store_true", help="Display BPM from MIDI Clock")
    parser.add_argument("--config", help="Path to .ini config file")

    args = parser.parse_args()

    if args.config:
        config = configparser.ConfigParser()
        config.read(args.config)
        cfg = config["DEFAULT"]
        args.in_port = args.in_port or cfg.get("in_port")
        args.out_port = args.out_port or cfg.get("out_port")

        args.midi_channel = int(cfg.get("midi_channel", args.midi_channel))

        args.beats_per_bar = int(cfg.get("beats_per_bar", args.beats_per_bar))
        args.ticks_per_beat = int(cfg.get("ticks_per_beat", args.ticks_per_beat))
        
        args.notes_per_bar = int(cfg.get("notes_per_bar", args.notes_per_bar))
        args.note = int(cfg.get("note", args.note))
        
        args.note_bar_1 = int(cfg.get("note_bar_1", args.note_bar_1))
        args.note_bar_2 = int(cfg.get("note_bar_2", args.note_bar_2))
        args.note_bar_4 = int(cfg.get("note_bar_4", args.note_bar_4))
        args.note_bar_8 = int(cfg.get("note_bar_8", args.note_bar_8))
        args.note_bar_16 = int(cfg.get("note_bar_16", args.note_bar_16))
        args.note_start = int(cfg.get("note_start", args.note_start))
        args.note_stop = int(cfg.get("note_stop", args.note_stop))
        args.show_bpm = cfg.get("show_bpm", str(args.show_bpm)).lower() in ("1", "true", "yes")

    return args

def send_note_on(midiout, note, velocity=100, channel=15):
    status = 0x90 | (channel-1 & 0x0F)
    midiout.send_message([status, note, velocity])

def main():
    args = parse_args_and_config()

    midi_in = rtmidi.MidiIn()
    midi_out = rtmidi.MidiOut()

    in_index, in_name = find_port(midi_in, args.in_port)
    out_index, out_name = find_port(midi_out, args.out_port)

    if in_index is None or out_index is None:
        print("❌ MIDI input/output port not found.")
        print("🔍 Available input ports:", list_ports(midi_in))
        print("🔍 Available output ports:", list_ports(midi_out))
        sys.exit(1)

    midi_in.open_port(in_index)
    # Enable reception of MIDI Clock
    midi_in.ignore_types(timing=False)

    midi_out.open_port(out_index)

    print(f"✅ Listening on: {in_name}")
    print(f"✅ Sending to: {out_name}")
    print("🎵 Notes: every bar = {}, every 2 = {}, every 4 = {}, every 8, every 16 = {}".format(
        args.note_bar_1, args.note_bar_2, args.note_bar_4, args.note_bar_8, args.note_bar_16
    ))
    print("▶️ Start note = {}, ⏹ Stop note = {}".format(args.note_start, args.note_stop))
    print("📈 BPM display: {}".format("On" if args.show_bpm else "Off"))

    clock_count = 0
    bar_count = 0
    last_clock_time = None

    print(f"ticks per beat = {args.ticks_per_beat}")
    print(f"beats per bar  = {args.beats_per_bar}")
    clocks_per_bar = args.ticks_per_beat * args.beats_per_bar
    print(f"clocks per bar  = {clocks_per_bar}")
    
    
    def midi_callback(event, data=None):
        nonlocal clock_count, bar_count, last_clock_time
        message, _ = event
        status = message[0]

        if status == MIDI_CLOCK:
            clock_count += 1

            if args.show_bpm:
                now = time.time()
                if last_clock_time:
                    delta = now - last_clock_time
                    bpm = 60.0 / (delta * 24) if delta > 0 else 0
                    print(f"BPM: {bpm:.2f}")
                last_clock_time = now

            if clock_count % clocks_per_bar == 0:
                bar_count += 1
                
                if not args.note == 0 and bar_count % args.notes_per_bar == 0:
                    send_note_on(midi_out, args.note, 100, args.midi_channel)
                if not args.note_bar_1 == 0:
                    send_note_on(midi_out, args.note_bar_1, 100, args.midi_channel)
                if not args.note_bar_2 == 0 and bar_count % 2 == 0:
                    send_note_on(midi_out, args.note_bar_2, 100, args.midi_channel)
                if not args.note_bar_4 == 0 and bar_count % 4 == 0:
                    send_note_on(midi_out, args.note_bar_4, 100, args.midi_channel)
                if not args.note_bar_8 == 0 and bar_count % 8 == 0:
                    send_note_on(midi_out, args.note_bar_8, 100, args.midi_channel)
                if not args.note_bar_16 == 0 and bar_count % 16 == 0:
                    send_note_on(midi_out, args.note_bar_16, 100, args.midi_channel)


        elif status == MIDI_START:
            print("▶️ Start received")
            send_note_on(midi_out, args.note_start, 100, args.midi_channel)

        elif status == MIDI_STOP:
            print("⏹ Stop received")
            send_note_on(midi_out, args.note_stop, 100, args.midi_channel)

    midi_in.set_callback(midi_callback)

    print("🎶 Running... Press Ctrl+C to stop.")
    try:
        while True:
            time.sleep(.1)
    except KeyboardInterrupt:
        print("🛑 Exiting.")
    finally:
        midi_in.close_port()
        midi_out.close_port()

if __name__ == "__main__":
    main()
