#include <cmath>
#include <vector>
#include <complex>
#include <cstdint>

#ifndef M_PI
#define M_PI 3.14159265358979323846
#endif

extern "C" {
    // algorithm: 0 = None, 1 = Twin Trap, 2 = Vortex Trap
#ifdef _WIN32
    __declspec(dllexport)
#endif
    void calculate_phases_and_packet(
        const double* cx, const double* cy, const double* cz,
        const double* tx, const double* ty, const double* tz,
        const double* amplitudes,
        int num_transducers, int num_points,
        int algorithm, double k,
        double* out_phases,
        uint8_t* out_packet
    ) {
        std::vector<std::complex<double>> complex_p(num_transducers, std::complex<double>(0.0, 0.0));

        // 1. Calculate phases
        for (int p = 0; p < num_points; ++p) {
            double p_tx = tx[p];
            double p_ty = ty[p];
            double p_tz = tz[p];

            for (int i = 0; i < num_transducers; ++i) {
                double dx = cx[i] - p_tx;
                double dy = cy[i] - p_ty;
                double dz = cz[i] - p_tz;

                double d = std::sqrt(dx*dx + dy*dy + dz*dz);
                double phase_focal = -d * k;

                double signature = 0.0;
                if (algorithm == 1) { // Twin Trap
                    if (dx > 0) signature = M_PI;
                } else if (algorithm == 2) { // Vortex Trap
                    signature = std::atan2(dy, dx);
                }

                double pt_phase = phase_focal + signature;
                double amp = amplitudes[i];
                
                complex_p[i] += std::polar(amp, pt_phase);
            }
        }

        // 2. Generate phases (0~2pi) and SonicSurface hardware packet
        // SonicSurface logic: PHASE_DIVS = 32
        // Start byte: 254
        // End byte: 253
        out_packet[0] = 254; 
        
        for (int i = 0; i < num_transducers; ++i) {
            double angle = std::arg(complex_p[i]);
            angle = std::fmod(angle, 2.0 * M_PI);
            if (angle < 0) {
                angle += 2.0 * M_PI;
            }
            out_phases[i] = angle;
            
            // Map to SonicSurface discretised phase (0 to 31)
            int phase_disc = static_cast<int>(std::round((angle / (2.0 * M_PI)) * 32.0));
            if (phase_disc >= 32) phase_disc = 0;
            if (phase_disc < 0) phase_disc = 0;
            
            out_packet[i + 1] = static_cast<uint8_t>(phase_disc);
        }
        
        out_packet[num_transducers + 1] = 253;
    }
}
