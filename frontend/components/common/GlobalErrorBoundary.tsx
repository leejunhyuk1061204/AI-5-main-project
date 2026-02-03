import React, { Component, ReactNode } from 'react';
import { View, Text, TouchableOpacity, StyleSheet, Dimensions } from 'react-native';
import { MaterialIcons } from '@expo/vector-icons';
// import * as Updates from 'expo-updates'; // Removed to prevent native module crash

interface Props {
    children: ReactNode;
}

interface State {
    hasError: boolean;
    error: Error | null;
}

/**
 * Global Error Boundary
 * Catches render errors and displays a fallback UI instead of crashing
 */
export class GlobalErrorBoundary extends Component<Props, State> {
    constructor(props: Props) {
        super(props);
        this.state = { hasError: false, error: null };
    }

    static getDerivedStateFromError(error: Error): State {
        return { hasError: true, error };
    }

    componentDidCatch(error: Error, errorInfo: React.ErrorInfo) {
        console.error('[GlobalErrorBoundary] Uncaught error:', error, errorInfo);
        // Here you would typically log to a service like Sentry or Crashlytics
    }

    handleRestart = async () => {
        try {
            // Native Module이 없을 수 있으므로 동적 require 사용
            const Updates = require('expo-updates');
            await Updates.reloadAsync();
        } catch (e) {
            console.error('[GlobalErrorBoundary] Restart failed (Updates module missing?):', e);
            // If reload fails (e.g. in development), just reset state
            this.setState({ hasError: false, error: null });

            // RN 기본 DevMenu reload 시도 (Dev 모드일 때)
            if (__DEV__) {
                const { DevSettings } = require('react-native');
                DevSettings.reload();
            }
        }
    };

    render() {
        if (this.state.hasError) {
            return (
                <View style={styles.container}>
                    <View style={styles.iconWrapper}>
                        <MaterialIcons name="error-outline" size={64} color="#ef4444" />
                    </View>
                    <Text style={styles.title}>문제가 발생했습니다</Text>
                    <Text style={styles.message}>
                        예기치 않은 오류가 발생하여 앱을 중단했습니다.{'\n'}
                        잠시 후 다시 시도해주세요.
                    </Text>

                    <TouchableOpacity
                        style={styles.button}
                        onPress={this.handleRestart}
                        activeOpacity={0.8}
                    >
                        <Text style={styles.buttonText}>앱 재시작</Text>
                    </TouchableOpacity>

                    {__DEV__ && (
                        <View style={styles.debugBox}>
                            <Text style={styles.debugText}>
                                {this.state.error?.toString()}
                            </Text>
                        </View>
                    )}
                </View>
            );
        }

        return this.props.children;
    }
}

const styles = StyleSheet.create({
    container: {
        flex: 1,
        backgroundColor: '#101922', // App Background
        alignItems: 'center',
        justifyContent: 'center',
        padding: 24,
    },
    iconWrapper: {
        marginBottom: 24,
        padding: 20,
        backgroundColor: 'rgba(239, 68, 68, 0.1)',
        borderRadius: 50,
        borderWidth: 1,
        borderColor: 'rgba(239, 68, 68, 0.2)',
    },
    title: {
        color: 'white',
        fontSize: 24,
        fontWeight: 'bold',
        marginBottom: 12,
    },
    message: {
        color: '#94a3b8',
        fontSize: 16,
        textAlign: 'center',
        lineHeight: 24,
        marginBottom: 40,
    },
    button: {
        backgroundColor: '#0d7ff2', // Primary
        paddingHorizontal: 32,
        paddingVertical: 16,
        borderRadius: 16,
        elevation: 4,
        shadowColor: '#0d7ff2',
        shadowOffset: { width: 0, height: 4 },
        shadowOpacity: 0.3,
        shadowRadius: 8,
    },
    buttonText: {
        color: 'white',
        fontSize: 16,
        fontWeight: 'bold',
    },
    debugBox: {
        marginTop: 40,
        padding: 16,
        backgroundColor: 'black',
        borderRadius: 8,
        width: '100%',
    },
    debugText: {
        color: '#ef4444',
        fontSize: 12,
        fontFamily: 'monospace',
    },
});
