import React from 'react';
import { View, Text, TouchableOpacity, Modal } from 'react-native';
import { useAlertStore } from '../../store/useAlertStore';
import { MaterialIcons } from '@expo/vector-icons';

export default function GlobalAlert() {
    const { visible, title, message, type, hideAlert, onConfirm, confirmText, cancelText, isDestructive } = useAlertStore();

    if (!visible) return null;

    const getColor = () => {
        switch (type) {
            case 'SUCCESS': return '#0d7ff2'; // primary token
            case 'ERROR': return '#ff6b6b';   // error token
            case 'WARNING': return '#f59e0b'; // warning token
            default: return '#0d7ff2';       // primary token
        }
    };

    const getIcon = () => {
        switch (type) {
            case 'SUCCESS': return 'check-circle';
            case 'ERROR': return 'error';
            case 'WARNING': return 'warning';
            default: return 'info';
        }
    };

    return (
        <Modal transparent visible={visible} animationType="fade">
            <View className="flex-1 bg-black/60 items-center justify-center px-8">
                <View className="bg-surface-dark w-full rounded-3xl p-6 border border-white/10 shadow-2xl">
                    <View className="items-center mb-4">
                        <View style={{ backgroundColor: `${getColor()}15` }} className="p-3 rounded-full">
                            <MaterialIcons name={getIcon()} size={32} color={getColor()} />
                        </View>
                    </View>

                    <Text className="text-white text-xl font-bold text-center mb-2">{title}</Text>
                    <Text className="text-text-secondary text-center leading-5 mb-8">{message}</Text>

                    <View className="flex-row gap-3">
                        <TouchableOpacity
                            onPress={hideAlert}
                            className="flex-1 bg-white/5 py-4 rounded-2xl border border-white/10"
                        >
                            <Text className="text-white text-center font-bold">{cancelText}</Text>
                        </TouchableOpacity>

                        {onConfirm && (
                            <TouchableOpacity
                                onPress={() => {
                                    onConfirm();
                                    hideAlert();
                                }}
                                className={`flex-1 py-4 rounded-2xl shadow-lg ${isDestructive ? 'bg-red-500' : 'bg-primary'}`}
                            >
                                <Text className="text-white text-center font-bold">{confirmText}</Text>
                            </TouchableOpacity>
                        )}
                    </View>
                </View>
            </View>
        </Modal>
    );
}
