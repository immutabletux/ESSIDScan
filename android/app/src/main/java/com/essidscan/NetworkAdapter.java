package com.essidscan;

import android.content.Context;
import android.view.LayoutInflater;
import android.view.View;
import android.view.ViewGroup;
import android.widget.ProgressBar;
import android.widget.TextView;
import androidx.annotation.NonNull;
import androidx.recyclerview.widget.RecyclerView;
import java.util.List;

public class NetworkAdapter extends RecyclerView.Adapter<NetworkAdapter.VH> {

    private List<WifiNetwork> networks;

    public NetworkAdapter(List<WifiNetwork> networks) {
        this.networks = networks;
    }

    public void update(List<WifiNetwork> nets) {
        this.networks = nets;
        notifyDataSetChanged();
    }

    @NonNull
    @Override
    public VH onCreateViewHolder(@NonNull ViewGroup parent, int viewType) {
        View v = LayoutInflater.from(parent.getContext())
                .inflate(R.layout.item_network, parent, false);
        return new VH(v);
    }

    @Override
    public void onBindViewHolder(@NonNull VH h, int pos) {
        WifiNetwork n = networks.get(pos);
        h.essid.setText(n.essid);
        h.bssid.setText(n.bssid);
        h.signal.setText(n.signalDbm + " dBm");
        h.channel.setText("CH " + n.channel + "  " + n.frequency);
        h.band.setText(n.band);
        h.encryption.setText(n.encryption);
        h.vendor.setText(n.vendor.isEmpty() ? "" : n.vendor);
        h.signalBar.setProgress(n.quality());

        // Colour signal bar by strength
        int q = n.quality();
        int color;
        if (q >= 67) color = 0xFF3fb950;      // green
        else if (q >= 34) color = 0xFFd29922;  // amber
        else color = 0xFFf85149;               // red
        h.signalBar.getProgressDrawable().setColorFilter(
                new android.graphics.PorterDuffColorFilter(color,
                        android.graphics.PorterDuff.Mode.SRC_IN));
    }

    @Override
    public int getItemCount() { return networks.size(); }

    static class VH extends RecyclerView.ViewHolder {
        TextView  essid, bssid, signal, channel, band, encryption, vendor;
        ProgressBar signalBar;

        VH(@NonNull View v) {
            super(v);
            essid      = v.findViewById(R.id.tv_essid);
            bssid      = v.findViewById(R.id.tv_bssid);
            signal     = v.findViewById(R.id.tv_signal);
            channel    = v.findViewById(R.id.tv_channel);
            band       = v.findViewById(R.id.tv_band);
            encryption = v.findViewById(R.id.tv_encryption);
            vendor     = v.findViewById(R.id.tv_vendor);
            signalBar  = v.findViewById(R.id.pb_signal);
        }
    }
}
