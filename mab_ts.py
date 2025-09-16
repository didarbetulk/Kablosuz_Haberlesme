# EPY: FHSS + Discounted TS Controller
# Warm-up: ED + FHSS (jam varsa FHSS siradaki ILK BOS kanala atla)
# After warm-up: ED gate, CURRENT JAM ise hedefi TS ile BOS adaylardan sec; jam yoksa kal
# Inputs (streams): 5 x float32  -> ed0..ed4 (power; dB icin ed_in_db=True, Mag^2 icin False)
# Outputs         : none (prints one TR line per slot)
# grc blok baglantilarina dikkat!!!
import time
import math
import random
import numpy as np
from gnuradio import gr

class fhss_ts_min_console(gr.sync_block):
    def __init__(self,
                 center_freq=2.410e9,
                 ch_offsets="[-8e6,-4e6,0,4e6,8e6]",
                 T_slot_s=1.0,
                 T_guard_s=0.06,
                 warmup_s=20.0,
                 # --- Hysteresis thresholds ---
                 threshold_db=8.0,          # high = nf*10^(dB/10)
                 hyst_ratio=0.8,            # low  = high*hyst_ratio (0.7..0.9)
                 ed_in_db=False,            # True: inputs are dB; False: linear (Mag^2)
                 # --- MAB / discounting ---
                 lambda_disc=0.98,
                 w_passive=0.25,
                 sticky_tau_slots=2,
                 beta_prior_floor=1.0,
                 # --- Runtime / sync ---
                 rng_seed=123456,
                 single_jammer=True,
                 start_align_next_s=True,
                 # --- Auto noise floor (linear domain) ---
                 auto_noise=True,
                 noise_calib_s=3.0):

        in_sigs = [np.float32]*5
        gr.sync_block.__init__(self,
            name="FHSS_TS_Console_EDGate_TSOnJam(EPY)",
            in_sig=in_sigs,
            out_sig=None)

        # params
        try:
            self.ch_offsets = list(eval(ch_offsets)) if isinstance(ch_offsets, str) else list(ch_offsets)
        except Exception:
            self.ch_offsets = [-8e6,-4e6,0.0,4e6,8e6]
        if len(self.ch_offsets) != 5:
            raise ValueError("ch_offsets must have 5 elements.")
        self.center_freq = float(center_freq)
        self.T_slot_s = float(T_slot_s)
        self.T_guard_s = float(T_guard_s)
        self.warmup_s = float(warmup_s)

        self.threshold_db = float(threshold_db)
        self.hyst_ratio = float(hyst_ratio)
        self.ed_in_db = bool(ed_in_db)

        self.lambda_disc = float(lambda_disc)
        self.w_passive = float(w_passive)
        self.sticky_tau_slots = int(sticky_tau_slots)
        self.beta_prior_floor = float(beta_prior_floor)

        # RNG: ayri akimlar; TS ve FHSS bagimsiz olsun diye iki tohum
        self.rng_ts = random.Random(int(rng_seed))
        self.rng_fhss = random.Random(int(rng_seed) + 1)

        self.single_jammer = bool(single_jammer)
        self.start_align_next_s = bool(start_align_next_s)

        self.auto_noise = bool(auto_noise)
        self.noise_calib_s = float(noise_calib_s)

        # state
        self.N = 5
        self.last_lin = [1e-12]*self.N   # linear power snapshot
        self.jam_state = [False]*self.N  # hysteresis memory
        self.alpha = [1.0]*self.N
        self.beta  = [1.0]*self.N
        self.alpha0 = [0.0]*self.N
        self.beta0  = [0.0]*self.N
        self.priors_frozen = False
        self.cur_idx = 2
        self.prev_idx = 2
        self.prev_slot = -1
        self.t0 = None
        self.sticky_left = 0

        # auto-noise estimator (linear)
        self._nf_est = None
        self._nf_count = 0
        self._nf_locked = False

        # last detected jammer index (-1 means none)
        self.last_jam_idx = -1

        # FHSS sirasi (deterministik permutasyon)
        self.fhss_seq = list(range(self.N))
        self.rng_fhss.shuffle(self.fhss_seq)

        # --- NEW: logging helpers ---
        self.line_no = 1
        self.warmup_announced = False

    # utils
    def _now_init_t0(self):
        now = time.time()
        if self.t0 is None:
            self.t0 = math.ceil(now) if self.start_align_next_s else now
        return now

    def _slot_index(self, now):
        return int(math.floor((now - self.t0)/self.T_slot_s))

    def _within_guard(self, now, slot_idx):
        slot_start = self.t0 + slot_idx*self.T_slot_s
        return (now - slot_start) >= self.T_guard_s

    @staticmethod
    def _db_to_lin(x_db):
        return 10.0**(float(x_db)/10.0)

    def _update_auto_noise(self, elapsed):
        if not self.auto_noise or self._nf_locked:
            return
        mn = float(min(self.last_lin))
        if self._nf_est is None:
            self._nf_est = mn
            self._nf_count = 1
        else:
            self._nf_count += 1
            self._nf_est += (mn - self._nf_est)/self._nf_count
        if elapsed >= self.noise_calib_s:
            self._nf_locked = True

    def _get_nf_lin(self):
        if self.auto_noise and (self._nf_est is not None):
            return float(self._nf_est)
        return float(min(self.last_lin))

    def _ed_to_flags(self):
        # Hysteresis thresholds around noise floor
        nf_lin = self._get_nf_lin()
        high = nf_lin * (10.0**(self.threshold_db/10.0))
        low  = high * self.hyst_ratio

        # update jam_state with hysteresis
        for i in range(self.N):
            p = self.last_lin[i]
            if p >= high:
                self.jam_state[i] = True
            elif p <= low:
                self.jam_state[i] = False

        # single-jammer enforce: keep only strongest if multiple
        if self.single_jammer and sum(1 for x in self.jam_state if x) > 1:
            k = int(np.argmax(np.array(self.last_lin)))
            self.jam_state = [ (i == k) for i in range(self.N) ]

        # store last jammer index
        if any(self.jam_state):
            # pick the True index
            self.last_jam_idx = self.jam_state.index(True)
        else:
            self.last_jam_idx = -1

        # success observation: below LOW and not jam
        s = [ 1.0 if (self.last_lin[i] <= low and not self.jam_state[i]) else 0.0 for i in range(self.N) ]
        return list(self.jam_state), s

    def _freeze_priors_if_needed(self, elapsed):
        if (not self.priors_frozen) and (elapsed >= self.warmup_s):
            self.alpha0 = [max(a, self.beta_prior_floor) for a in self.alpha]
            self.beta0  = [max(b, self.beta_prior_floor) for b in self.beta]
            self.priors_frozen = True

    def _discount_posteriors(self):
        for i in range(self.N):
            self.alpha[i] = max(self.alpha0[i] + self.lambda_disc*(self.alpha[i]-self.alpha0[i]), self.beta_prior_floor)
            self.beta[i]  = max(self.beta0[i]  + self.lambda_disc*(self.beta[i] -self.beta0[i]),  self.beta_prior_floor)

    def _ts_pick(self, jam):
        # choose among non-jam candidates
        cand = [i for i in range(self.N) if not jam[i]]
        theta = []
        for i in cand:
            a = max(self.alpha[i], self.beta_prior_floor)
            b = max(self.beta[i],  self.beta_prior_floor)
            th = self.rng_ts.betavariate(a, b)
            theta.append((th, i))
        theta.sort(reverse=True)
        return theta[0][1]

    def _fhss_next_free(self, jam):
        # return first FREE channel in fhss_seq AFTER current position
        try:
            pos = self.fhss_seq.index(self.cur_idx)
        except ValueError:
            pos = 0
        for step in range(1, self.N + 1):
            cand = self.fhss_seq[(pos + step) % self.N]
            if not jam[cand]:
                return cand
        return self.cur_idx  # tek-jammer icin buraya gelmez

    def _post_mean(self):
        acc = []
        for i in range(self.N):
            a = max(self.alpha[i], self.beta_prior_floor)
            b = max(self.beta[i],  self.beta_prior_floor)
            acc.append(a/(a+b))
        return acc

    # --- NEW: numbered print ---
    def _print_line(self):
        acc = self._post_mean()
        jam_str = "-" if self.last_jam_idx < 0 else str(int(self.last_jam_idx+1))
        line = "{:d})  onceki kanal={:d} anlik kanal={:d} dogruluk=[{:.3f},{:.3f},{:.3f},{:.3f},{:.3f}] jammer={}".format(
            int(self.line_no),
            int(self.prev_idx+1), int(self.cur_idx+1),
            float(acc[0]), float(acc[1]), float(acc[2]), float(acc[3]), float(acc[4]),
            jam_str
        )
        print(line, flush=True)
        self.line_no += 1

    # --- NEW: warm-up separator once ---
    def _print_warmup_done(self):
        print("------------------------------", flush=True)
        print("20 saniyelik warmup tamamlandi.", flush=True)
        print("------------------------------", flush=True)

    def work(self, input_items, output_items):
        # capture latest ED values, convert to linear if needed
        n_in = min([len(input_items[i]) for i in range(self.N)]) if self.N>0 else 0
        if n_in > 0:
            for i in range(self.N):
                v = float(input_items[i][n_in-1])
                self.last_lin[i] = (10.0**(v/10.0)) if self.ed_in_db else v

        now = self._now_init_t0()
        elapsed = now - self.t0

        # auto noise calibration
        self._update_auto_noise(elapsed)

        # --- NEW: announce warm-up completion exactly once ---
        if (not self.warmup_announced) and (elapsed >= self.warmup_s):
            self._print_warmup_done()
            self.warmup_announced = True

        slot_idx = self._slot_index(now)
        self._freeze_priors_if_needed(elapsed)

        if (slot_idx != self.prev_slot) and self._within_guard(now, slot_idx):
            self.prev_slot = slot_idx
            jam, s = self._ed_to_flags()

            self.prev_idx = self.cur_idx

            if elapsed < self.warmup_s:
                # accumulate priors (ED-only phase)
                for i in range(self.N):
                    self.alpha[i] += s[i]
                    self.beta[i]  += (1.0 - s[i])

                # ED + FHSS: eger CURRENT jam ise, FHSS sirada ilk BOS kanala atla
                if jam[self.cur_idx]:
                    pick = self._fhss_next_free(jam)
                else:
                    pick = self.cur_idx

            else:
                # discounted TS calistir; YALNIZ CURRENT jam ise TS ile hedef belirle
                self._discount_posteriors()

                if jam[self.cur_idx]:
                    pick = self._ts_pick(jam)      # non-jam adaylar arasindan
                else:
                    pick = self.cur_idx            # jam yoksa kal (kesif yok)

                # update posteriors (selected full, others passive)
                for i in range(self.N):
                    if i == pick:
                        self.alpha[i] += s[i]
                        self.beta[i]  += (1.0 - s[i])
                    else:
                        self.alpha[i] += self.w_passive * s[i]
                        self.beta[i]  += self.w_passive * (1.0 - s[i])

            # apply selection + sticky
            if pick != self.cur_idx:
                self.cur_idx = pick
                self.sticky_left = self.sticky_tau_slots
            else:
                if self.sticky_left > 0:
                    self.sticky_left -= 1

            # print once per slot
            self._print_line()

        return n_in
