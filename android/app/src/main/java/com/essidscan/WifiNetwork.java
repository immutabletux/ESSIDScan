package com.essidscan;

public class WifiNetwork {
    public final String essid;
    public final String bssid;
    public final int    signalDbm;
    public final int    channel;
    public final String frequency;
    public final String band;
    public final String encryption;
    public final String vendor;

    public WifiNetwork(String essid, String bssid, int signalDbm,
                       int channel, String frequency, String band,
                       String encryption, String vendor) {
        this.essid      = essid.isEmpty() ? "(hidden)" : essid;
        this.bssid      = bssid;
        this.signalDbm  = signalDbm;
        this.channel    = channel;
        this.frequency  = frequency;
        this.band       = band;
        this.encryption = encryption;
        this.vendor     = vendor;
    }

    /** 0–100 quality from dBm */
    public int quality() {
        if (signalDbm <= -100) return 0;
        if (signalDbm >= -50)  return 100;
        return 2 * (signalDbm + 100);
    }

    /** Signal bars 0–4 */
    public int bars() {
        int q = quality();
        if (q >= 75) return 4;
        if (q >= 50) return 3;
        if (q >= 25) return 2;
        if (q >  0)  return 1;
        return 0;
    }

    static int freqToChannel(int freqMhz) {
        if (freqMhz >= 2412 && freqMhz <= 2484) return (freqMhz - 2407) / 5;
        if (freqMhz >= 5000)                    return (freqMhz - 5000) / 5;
        return 0;
    }

    static String freqToGhz(int freqMhz) {
        return String.format("%.3f GHz", freqMhz / 1000.0);
    }

    static String capabilitiesToEncryption(String caps) {
        if (caps == null) return "Open";
        if (caps.contains("WPA3") || caps.contains("SAE")) return "WPA3";
        if (caps.contains("WPA2") || caps.contains("RSN")) return "WPA2";
        if (caps.contains("WPA"))  return "WPA";
        if (caps.contains("WEP"))  return "WEP";
        return "Open";
    }
}
