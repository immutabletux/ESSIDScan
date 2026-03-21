package com.essidscan;

import android.Manifest;
import android.content.BroadcastReceiver;
import android.content.Context;
import android.content.Intent;
import android.content.IntentFilter;
import android.content.pm.PackageManager;
import android.net.wifi.ScanResult;
import android.net.wifi.WifiManager;
import android.os.Build;
import android.os.Bundle;
import android.view.Menu;
import android.view.MenuItem;
import android.widget.TextView;
import android.widget.Toast;
import androidx.annotation.NonNull;
import androidx.appcompat.app.AppCompatActivity;
import androidx.appcompat.widget.Toolbar;
import androidx.core.app.ActivityCompat;
import androidx.recyclerview.widget.LinearLayoutManager;
import androidx.recyclerview.widget.RecyclerView;
import androidx.swiperefreshlayout.widget.SwipeRefreshLayout;
import com.google.android.material.snackbar.Snackbar;
import java.util.ArrayList;
import java.util.Collections;
import java.util.List;

public class MainActivity extends AppCompatActivity {

    private static final int REQ_PERMISSIONS = 1;

    private WifiManager        wifiManager;
    private NetworkAdapter     adapter;
    private SwipeRefreshLayout swipeRefresh;
    private TextView           tvCount;
    private boolean            receiverRegistered = false;

    private final BroadcastReceiver scanReceiver = new BroadcastReceiver() {
        @Override
        public void onReceive(Context ctx, Intent intent) {
            loadScanResults();
        }
    };

    @Override
    protected void onCreate(Bundle savedInstanceState) {
        super.onCreate(savedInstanceState);
        setContentView(R.layout.activity_main);

        Toolbar toolbar = findViewById(R.id.toolbar);
        setSupportActionBar(toolbar);
        if (getSupportActionBar() != null) {
            getSupportActionBar().setTitle("ESSIDscan");
        }

        wifiManager  = (WifiManager) getApplicationContext()
                            .getSystemService(Context.WIFI_SERVICE);
        swipeRefresh = findViewById(R.id.swipe_refresh);
        tvCount      = findViewById(R.id.tv_count);

        RecyclerView rv = findViewById(R.id.recycler);
        rv.setLayoutManager(new LinearLayoutManager(this));
        adapter = new NetworkAdapter(new ArrayList<>());
        rv.setAdapter(adapter);

        swipeRefresh.setColorSchemeColors(0xFF79c0ff, 0xFF3fb950, 0xFFd29922);
        swipeRefresh.setOnRefreshListener(this::startScan);

        checkPermissionsAndScan();
    }

    @Override
    protected void onResume() {
        super.onResume();
        try {
            IntentFilter filter = new IntentFilter(WifiManager.SCAN_RESULTS_AVAILABLE_ACTION);
            registerReceiver(scanReceiver, filter);
            receiverRegistered = true;
        } catch (Exception e) {
            receiverRegistered = false;
        }
    }

    @Override
    protected void onPause() {
        super.onPause();
        if (receiverRegistered) {
            try { unregisterReceiver(scanReceiver); } catch (Exception ignored) {}
            receiverRegistered = false;
        }
    }

    @Override
    public boolean onCreateOptionsMenu(Menu menu) {
        getMenuInflater().inflate(R.menu.main_menu, menu);
        return true;
    }

    @Override
    public boolean onOptionsItemSelected(@NonNull MenuItem item) {
        if (item.getItemId() == R.id.action_scan) {
            swipeRefresh.setRefreshing(true);
            startScan();
            return true;
        }
        return super.onOptionsItemSelected(item);
    }

    // ── Permissions ──────────────────────────────────────────────────────────────

    private boolean hasRequiredPermissions() {
        if (ActivityCompat.checkSelfPermission(this, Manifest.permission.ACCESS_FINE_LOCATION)
                != PackageManager.PERMISSION_GRANTED) {
            return false;
        }
        if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.TIRAMISU) {
            return ActivityCompat.checkSelfPermission(this,
                    Manifest.permission.NEARBY_WIFI_DEVICES)
                    == PackageManager.PERMISSION_GRANTED;
        }
        return true;
    }

    private void checkPermissionsAndScan() {
        List<String> toRequest = new ArrayList<>();
        if (ActivityCompat.checkSelfPermission(this, Manifest.permission.ACCESS_FINE_LOCATION)
                != PackageManager.PERMISSION_GRANTED) {
            toRequest.add(Manifest.permission.ACCESS_FINE_LOCATION);
        }
        if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.TIRAMISU) {
            if (ActivityCompat.checkSelfPermission(this,
                    Manifest.permission.NEARBY_WIFI_DEVICES)
                    != PackageManager.PERMISSION_GRANTED) {
                toRequest.add(Manifest.permission.NEARBY_WIFI_DEVICES);
            }
        }
        if (toRequest.isEmpty()) {
            startScan();
        } else {
            ActivityCompat.requestPermissions(this,
                    toRequest.toArray(new String[0]), REQ_PERMISSIONS);
        }
    }

    @Override
    public void onRequestPermissionsResult(int requestCode,
            @NonNull String[] permissions, @NonNull int[] grantResults) {
        super.onRequestPermissionsResult(requestCode, permissions, grantResults);
        if (requestCode != REQ_PERMISSIONS) return;

        if (hasRequiredPermissions()) {
            startScan();
        } else {
            // At least try to show whatever cached results exist
            loadScanResults();
            Snackbar.make(findViewById(android.R.id.content),
                    "Location permission required for WiFi scanning",
                    Snackbar.LENGTH_LONG)
                    .setAction("Retry", v -> checkPermissionsAndScan())
                    .show();
        }
    }

    // ── Scanning ─────────────────────────────────────────────────────────────────

    @SuppressWarnings("deprecation")
    private void startScan() {
        if (wifiManager == null) {
            Toast.makeText(this, "WiFi not available on this device",
                    Toast.LENGTH_SHORT).show();
            swipeRefresh.setRefreshing(false);
            return;
        }
        if (!wifiManager.isWifiEnabled()) {
            Snackbar.make(findViewById(android.R.id.content),
                    "WiFi is disabled — enable it to scan",
                    Snackbar.LENGTH_LONG).show();
            loadScanResults();
            swipeRefresh.setRefreshing(false);
            return;
        }
        if (!hasRequiredPermissions()) {
            checkPermissionsAndScan();
            return;
        }

        swipeRefresh.setRefreshing(true);
        try {
            boolean started = wifiManager.startScan();
            if (!started) {
                // Throttled — show cached results
                loadScanResults();
                swipeRefresh.setRefreshing(false);
                Toast.makeText(this,
                        "Scan throttled — showing cached results",
                        Toast.LENGTH_SHORT).show();
            }
        } catch (SecurityException e) {
            loadScanResults();
            swipeRefresh.setRefreshing(false);
            Toast.makeText(this, "Permission denied for scan", Toast.LENGTH_SHORT).show();
        }
    }

    private void loadScanResults() {
        if (wifiManager == null) return;
        if (!hasRequiredPermissions()) return;

        List<ScanResult> raw;
        try {
            raw = wifiManager.getScanResults();
        } catch (SecurityException e) {
            Toast.makeText(this, "Cannot read scan results: permission denied",
                    Toast.LENGTH_SHORT).show();
            swipeRefresh.setRefreshing(false);
            return;
        }

        List<WifiNetwork> nets = new ArrayList<>();
        for (ScanResult sr : raw) {
            try {
                int    freq    = sr.frequency;
                int    channel = WifiNetwork.freqToChannel(freq);
                String freqGhz = WifiNetwork.freqToGhz(freq);
                String band    = freq >= 5000 ? "5 GHz" : "2.4 GHz";
                String enc     = WifiNetwork.capabilitiesToEncryption(sr.capabilities);
                String vendor  = ouiVendor(sr.BSSID);
                String ssid    = (sr.SSID != null) ? sr.SSID.replace("\"", "") : "";
                nets.add(new WifiNetwork(ssid, sr.BSSID, sr.level,
                        channel, freqGhz, band, enc, vendor));
            } catch (Exception ignored) {}
        }

        Collections.sort(nets, (a, b) -> b.signalDbm - a.signalDbm);
        adapter.update(nets);
        tvCount.setText(nets.size() + " networks");
        swipeRefresh.setRefreshing(false);
    }

    /** Minimal OUI vendor lookup from BSSID prefix */
    private String ouiVendor(String bssid) {
        if (bssid == null || bssid.length() < 8) return "";
        String oui = bssid.substring(0, 8).toUpperCase();
        switch (oui) {
            case "00:50:F2": return "Microsoft";
            case "00:0C:E7": return "Cisco";
            case "00:17:F2": return "Apple";
            case "A4:C3:F0": return "Apple";
            case "00:1A:11": return "Google";
            case "F8:8F:CA": return "Google";
            case "00:26:BB": return "Apple";
            case "18:FE:34": return "Espressif";
            case "00:1E:64": return "Samsung";
            case "00:23:76": return "Samsung";
            default:         return "";
        }
    }
}
