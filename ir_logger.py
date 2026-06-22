
import time
 
try:
    import RPi.GPIO as GPIO
except (ImportError, RuntimeError):
    raise SystemExit(
        "RPi.GPIO not available -- this logger must run on the Pi itself."
    )
 
IR_PIN = 18  # BCM numbering. Physical pin 12.
 
# NEC protocol timing (microseconds), with generous tolerances because
# cheap remotes and Python timing are both a little sloppy.
NEC_LEADER_PULSE = 9000
NEC_LEADER_SPACE = 4500
NEC_BIT_PULSE = 562
NEC_ZERO_SPACE = 562
NEC_ONE_SPACE = 1687
TOL = 0.35  # +/-35% tolerance on all timings
 
 
def within(value, target, tol=TOL):
    return abs(value - target) <= target * tol
 
 
def read_pulses(timeout_s=0.25, idle_gap_us=10000):
    """
    Wait for IR activity, then capture the sequence of level-change
    durations (in microseconds) until the line goes idle. Returns a list
    of (level, duration_us) tuples, or None if nothing happened.
 
    The VS838 output idles HIGH and pulls LOW when it sees 38kHz carrier,
    so 'activity' begins on the first falling edge.
    """
    start_wait = time.monotonic()
    # Wait for the line to drop (start of a transmission).
    while GPIO.input(IR_PIN) == 1:
        if time.monotonic() - start_wait > timeout_s:
            return None
 
    edges = []
    last_change = time.monotonic()
    last_level = 0  # we just saw it go low
 
    while True:
        level = GPIO.input(IR_PIN)
        now = time.monotonic()
        if level != last_level:
            dur_us = (now - last_change) * 1_000_000
            edges.append((last_level, dur_us))
            last_change = now
            last_level = level
        else:
            # If the line has sat idle (high) longer than idle_gap, we're done.
            if level == 1 and (now - last_change) * 1_000_000 > idle_gap_us:
                break
    return edges
 
 
def decode_nec(edges):
    """
    Try to decode a captured edge list as NEC. Returns a 32-bit int on
    success, or None if it doesn't look like valid NEC.
    """
    if len(edges) < 4:
        return None
 
    # edges alternate (low=pulse, high=space). Find the leader.
    # First entry should be a ~9ms low pulse, second a ~4.5ms high space.
    if not (edges[0][0] == 0 and within(edges[0][1], NEC_LEADER_PULSE)):
        return None
    if not (edges[1][0] == 1 and within(edges[1][1], NEC_LEADER_SPACE)):
        return None
 
    bits = []
    # After the leader, bits come as (562us pulse, variable space) pairs.
    i = 2
    while i + 1 < len(edges) and len(bits) < 32:
        pulse_level, pulse_dur = edges[i]
        space_level, space_dur = edges[i + 1]
        if pulse_level != 0 or space_level != 1:
            break
        if not within(pulse_dur, NEC_BIT_PULSE):
            break
        if within(space_dur, NEC_ONE_SPACE):
            bits.append(1)
        elif within(space_dur, NEC_ZERO_SPACE):
            bits.append(0)
        else:
            break
        i += 2
 
    if len(bits) < 32:
        return None
 
    value = 0
    for b in bits[:32]:
        value = (value << 1) | b
    return value
 
 
def main():
    GPIO.setmode(GPIO.BCM)
    GPIO.setup(IR_PIN, GPIO.IN)
 
    print("IR logger running. Point the remote at the VS838 and press buttons.")
    print("Each recognized press prints its code. Ctrl+C to quit.\n")
    print(f"{'CODE (hex)':<14}{'addr':<8}{'cmd':<8}note")
    print("-" * 44)
 
    seen = {}
    last_code = None
    last_time = 0.0
 
    try:
        while True:
            edges = read_pulses()
            if not edges:
                continue
 
            code = decode_nec(edges)
            now = time.monotonic()
 
            if code is None:
                # Could be a repeat frame (NEC sends a short "still held"
                # burst) or a non-NEC remote. Show raw timing so it's not
                # a silent failure.
                durations = [round(d) for _, d in edges[:6]]
                print(f"{'(undecoded)':<14}{'':<8}{'':<8}raw start us={durations}")
                continue
 
            # NEC packs address in upper 16 bits, command in middle byte.
            addr = (code >> 16) & 0xFFFF
            cmd = (code >> 8) & 0xFF
 
            # Suppress duplicate prints from button bounce/hold within 250ms.
            if code == last_code and (now - last_time) < 0.25:
                last_time = now
                continue
 
            note = ""
            if code not in seen:
                seen[code] = True
                note = "** NEW **"
            print(f"0x{code:08X}    0x{addr:04X}  0x{cmd:02X}    {note}")
 
            last_code = code
            last_time = now
 
    except KeyboardInterrupt:
        print("\n\nButtons seen this session:")
        for c in seen:
            print(f"  0x{c:08X}  (cmd 0x{(c >> 8) & 0xFF:02X})")
        print("\nWrite these down next to which button you pressed for each.")
    finally:
        GPIO.cleanup()
 
 
if __name__ == "__main__":
    main()
 
