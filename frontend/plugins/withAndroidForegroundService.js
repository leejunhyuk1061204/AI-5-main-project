const { withAndroidManifest } = require('@expo/config-plugins');

const withAndroidForegroundService = (config) => {
    return withAndroidManifest(config, async (config) => {
        const androidManifest = config.modResults;
        const mainApplication = androidManifest.manifest.application[0];

        if (!mainApplication.service) {
            mainApplication.service = [];
        }

        // Add react-native-background-actions service
        const serviceName = 'com.asterinet.react.bgactions.RNBackgroundActionsTask';
        const existingService = mainApplication.service.find(
            (s) => s.$['android:name'] === serviceName
        );

        if (!existingService) {
            mainApplication.service.push({
                $: {
                    'android:name': serviceName,
                    'android:foregroundServiceType': 'connectedDevice',
                },
            });
        }

        return config;
    });
};

module.exports = withAndroidForegroundService;
