import React, { useEffect, useRef } from 'react';
import { View, Text, TouchableOpacity, Modal, Animated, StyleSheet, Platform, Dimensions } from 'react-native';
import { MaterialIcons } from '@expo/vector-icons';
import { BlurView } from 'expo-blur';
import { useErrorStore } from '../../store/useErrorStore';

const { width } = Dimensions.get('window');

/**
 * Global Custom Error Modal
 * Premium dark mode design with glassmorphism
 */
export default function CustomErrorModal() {
    const { isVisible, title, message, type, onRetry, hideError } = useErrorStore();
    const scaleAnim = useRef(new Animated.Value(0.9)).current;
    const opacityAnim = useRef(new Animated.Value(0)).current;

    useEffect(() => {
        if (isVisible) {
            Animated.parallel([
                Animated.spring(scaleAnim, {
                    toValue: 1,
                    friction: 8,
                    tension: 40,
                    useNativeDriver: true,
                }),
                Animated.timing(opacityAnim, {
                    toValue: 1,
                    duration: 200,
                    useNativeDriver: true,
                }),
            ]).start();
        } else {
            Animated.timing(opacityAnim, {
                toValue: 0,
                duration: 150,
                useNativeDriver: true,
            }).start(({ finished }) => {
                if (finished) scaleAnim.setValue(0.9);
            });
        }
    }, [isVisible]);

    if (!isVisible) return null;

    const getIcon = () => {
        switch (type) {
            case 'WARNING': return { name: 'warning-amber' as const, color: '#f59e0b' }; // Amber-500
            case 'INFO': return { name: 'info-outline' as const, color: '#3b82f6' }; // Blue-500
            case 'ERROR':
            default: return { name: 'error-outline' as const, color: '#ef4444' }; // Red-500
        }
    };

    const iconData = getIcon();

    return (
        <Modal
            transparent
            visible={isVisible}
            animationType="none"
            onRequestClose={hideError}
        >
            <View style={styles.overlay}>
                {Platform.OS === 'ios' ? (
                    <BlurView intensity={30} tint="dark" style={StyleSheet.absoluteFill} />
                ) : (
                    <View style={styles.androidDim} />
                )}

                <Animated.View style={[styles.modalContainer, { opacity: opacityAnim, transform: [{ scale: scaleAnim }] }]}>
                    {/* Icon Header */}
                    <View style={[styles.iconWrapper, { backgroundColor: `${iconData.color}20`, borderColor: `${iconData.color}40` }]}>
                        <MaterialIcons name={iconData.name} size={36} color={iconData.color} />
                    </View>

                    {/* Content */}
                    <Text style={styles.title}>{title}</Text>
                    <Text style={styles.message}>{message}</Text>

                    {/* Actions */}
                    <View style={styles.actionContainer}>
                        {onRetry ? (
                            <>
                                <TouchableOpacity style={styles.cancelButton} onPress={hideError} activeOpacity={0.7}>
                                    <Text style={styles.cancelButtonText}>취소</Text>
                                </TouchableOpacity>
                                <TouchableOpacity style={styles.confirmButton} onPress={() => { hideError(); onRetry(); }} activeOpacity={0.7}>
                                    <Text style={styles.confirmButtonText}>재시도</Text>
                                </TouchableOpacity>
                            </>
                        ) : (
                            <TouchableOpacity style={styles.fullButton} onPress={hideError} activeOpacity={0.7}>
                                <Text style={styles.fullButtonText}>확인</Text>
                            </TouchableOpacity>
                        )}
                    </View>
                </Animated.View>
            </View>
        </Modal>
    );
}

const styles = StyleSheet.create({
    overlay: {
        flex: 1,
        justifyContent: 'center',
        alignItems: 'center',
        backgroundColor: 'rgba(0,0,0,0.6)',
    },
    androidDim: {
        ...StyleSheet.absoluteFillObject,
        backgroundColor: 'rgba(0,0,0,0.8)',
    },
    modalContainer: {
        width: width * 0.82,
        backgroundColor: '#1b2127', // Surface Card Color
        borderRadius: 24,
        padding: 24,
        alignItems: 'center',
        borderWidth: 1,
        borderColor: 'rgba(255,255,255,0.1)',
        shadowColor: '#000',
        shadowOffset: { width: 0, height: 10 },
        shadowOpacity: 0.5,
        shadowRadius: 20,
        elevation: 10,
    },
    iconWrapper: {
        width: 72,
        height: 72,
        borderRadius: 36,
        justifyContent: 'center',
        alignItems: 'center',
        marginBottom: 20,
        borderWidth: 1,
    },
    title: {
        color: 'white',
        fontSize: 19,
        fontWeight: '700',
        marginBottom: 10,
        textAlign: 'center',
        letterSpacing: -0.5,
    },
    message: {
        color: '#94a3b8', // Text Dim
        fontSize: 15,
        lineHeight: 22,
        textAlign: 'center',
        marginBottom: 28,
        paddingHorizontal: 10,
    },
    actionContainer: {
        flexDirection: 'row',
        width: '100%',
        gap: 12,
    },
    cancelButton: {
        flex: 1,
        paddingVertical: 14,
        borderRadius: 14,
        backgroundColor: 'rgba(255,255,255,0.05)',
        alignItems: 'center',
        justifyContent: 'center',
        borderWidth: 1,
        borderColor: 'rgba(255,255,255,0.05)',
    },
    cancelButtonText: {
        color: '#94a3b8',
        fontSize: 15,
        fontWeight: '600',
    },
    confirmButton: {
        flex: 1,
        paddingVertical: 14,
        borderRadius: 14,
        backgroundColor: '#0d7ff2', // Primary
        alignItems: 'center',
        justifyContent: 'center',
    },
    confirmButtonText: {
        color: 'white',
        fontSize: 15,
        fontWeight: '700',
    },
    fullButton: {
        width: '100%',
        paddingVertical: 14,
        borderRadius: 14,
        backgroundColor: '#0d7ff2', // Primary
        alignItems: 'center',
        justifyContent: 'center',
    },
    fullButtonText: {
        color: 'white',
        fontSize: 15,
        fontWeight: '700',
    },
});
