const {
    withAndroidManifest,
    withInfoPlist,
    createRunOncePlugin,
} = require('@expo/config-plugins');

const withBleManager = (config) => {
    // Android Permissions
    config = withAndroidManifest(config, (config) => {
        const androidManifest = config.modResults;
        const permissions = [
            'android.permission.BLUETOOTH',
            'android.permission.BLUETOOTH_ADMIN',
            'android.permission.BLUETOOTH_CONNECT',
            'android.permission.BLUETOOTH_SCAN',
            'android.permission.ACCESS_FINE_LOCATION',
        ];

        if (!androidManifest.manifest['uses-permission']) {
            androidManifest.manifest['uses-permission'] = [];
        }

        permissions.forEach((permission) => {
            const hasPermission = androidManifest.manifest['uses-permission'].some(
                (props) => props['$']['android:name'] === permission
            );
            if (!hasPermission) {
                androidManifest.manifest['uses-permission'].push({
                    $: { 'android:name': permission },
                });
            }
        });

        return config;
    });

    // iOS Permissions
    config = withInfoPlist(config, (config) => {
        config.modResults.NSBluetoothAlwaysUsageDescription =
            config.modResults.NSBluetoothAlwaysUsageDescription ||
            'App requires Bluetooth to connect to OBD devices.';

        // For iOS 12 and below (optional but good for compatibility)
        config.modResults.NSBluetoothPeripheralUsageDescription =
            config.modResults.NSBluetoothPeripheralUsageDescription ||
            'App requires Bluetooth to connect to OBD devices.';

        return config;
    });

    return config;
};

module.exports = createRunOncePlugin(withBleManager, 'withBleManager', '1.0.0');
