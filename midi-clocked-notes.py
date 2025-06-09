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

    parser.add_argument("--note-clock-1", type=int, default=60, help="Note every clock")
    parser.add_argument("--note-clock-2", type=int, default=61, help="Note every 2 clocks")
    parser.add_argument("--note-clock-4", type=int, default=62, help="Note every 4 clocks")
    parser.add_argument("--note-clock-8", type=int, default=63, help="Note every 8 clocks")

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
        args.note_clock_1 = int(cfg.get("note_clock_1", args.note_clock_1))
        args.note_clock_2 = int(cfg.get("note_clock_2", args.note_clock_2))
        args.note_clock_4 = int(cfg.get("note_clock_4", args.note_clock_4))
        args.note_clock_8 = int(cfg.get("note_clock_8", args.note_clock_8))
        args.note_start = int(cfg.get("note_start", args.note_start))
        args.note_stop = int(cfg.get("note_stop", args.note_stop))
        args.show_bpm = cfg.get("show_bpm", str(args.show_bpm)).lower() in ("1", "true", "yes")

    return args

def send_note_on(midiout, note, velocity=100, channel=0):
    status = 0x90 | (channel & 0x0F)
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
    print("🎵 Notes: every clock = {}, every 2 = {}, every 4 = {}, every 8 = {}".format(
        args.note_clock_1, args.note_clock_2, args.note_clock_4, args.note_clock_8
    ))
    print("▶️ Start note = {}, ⏹ Stop note = {}".format(args.note_start, args.note_stop))
    print("📈 BPM display: {}".format("On" if args.show_bpm else "Off"))

    clock_count = 0
    last_clock_time = None

    def midi_callback(event, data=None):
        nonlocal clock_count, last_clock_time
        message, _ = event
        status = message[0]

        if status == MIDI_CLOCK:
            clock_count += 1

            send_note_on(midi_out, args.note_clock_1)
            if clock_count % 2 == 0:
                send_note_on(midi_out, args.note_clock_2)
            if clock_count % 4 == 0:
                send_note_on(midi_out, args.note_clock_4)
            if clock_count % 8 == 0:
                send_note_on(midi_out, args.note_clock_8)

            if args.show_bpm:
                now = time.time()
                if last_clock_time:
                    delta = now - last_clock_time
                    bpm = 60.0 / (delta * 24) if delta > 0 else 0
                    print(f"BPM: {bpm:.2f}")
                last_clock_time = now

        elif status == MIDI_START:
            print("▶️ Start received")
            send_note_on(midi_out, args.note_start)

        elif status == MIDI_STOP:
            print("⏹ Stop received")
            send_note_on(midi_out, args.note_stop)

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
