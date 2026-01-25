import React from 'react';
import { View, Text, TouchableOpacity, Modal } from 'react-native';
import { useAlertStore } from '../../store/useAlertStore';
import { MaterialIcons } from '@expo/vector-icons';

export default function GlobalAlert() {
    const { visible, title, message, type, hideAlert, onConfirm } = useAlertStore();

    if (!visible) return null;

    const getColor = () => {
        switch (type) {
            case 'SUCCESS': return '#10b981';
            case 'ERROR': return '#ef4444';
            case 'WARNING': return '#f59e0b';
            default: return '#3b82f6';
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
                <View className="bg-[#1e293b] w-full rounded-3xl p-6 border border-white/10 shadow-2xl">
                    <View className="items-center mb-4">
                        <View style={{ backgroundColor: `${getColor()}20` }} className="p-3 rounded-full">
                            <MaterialIcons name={getIcon()} size={32} color={getColor()} />
                        </View>
                    </View>

                    <Text className="text-white text-xl font-bold text-center mb-2">{title}</Text>
                    <Text className="text-slate-400 text-center leading-5 mb-8">{message}</Text>

                    <View className="flex-row gap-3">
                        <TouchableOpacity
                            onPress={hideAlert}
                            className="flex-1 bg-white/5 py-4 rounded-2xl border border-white/5"
                        >
                            <Text className="text-white text-center font-bold">닫기</Text>
                        </TouchableOpacity>

                        {onConfirm && (
                            <TouchableOpacity
                                onPress={() => {
                                    onConfirm();
                                    hideAlert();
                                }}
                                style={{ backgroundColor: getColor() }}
                                className="flex-1 py-4 rounded-2xl shadow-lg"
                            >
                                <Text className="text-white text-center font-bold">확인</Text>
                            </TouchableOpacity>
                        )}
                    </View>
                </View>
            </View>
        </Modal>
    );
}
