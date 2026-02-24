import React from 'react';
import { View, Text, Modal, ActivityIndicator } from 'react-native';
import { useBleStore } from '../../store/useBleStore';

/**
 * BLE OBD 연결 중일 때 전체 화면에 표시되는 오버레이
 * useBleStore의 status가 'connecting'일 때 자동 표시
 */
export default function ObdConnectingOverlay() {
    const status = useBleStore(state => state.status);

    if (status !== 'connecting') return null;

    return (
        <Modal transparent visible animationType="fade">
            <View className="flex-1 bg-black/70 items-center justify-center px-8">
                <View className="bg-surface-dark w-full rounded-3xl p-8 border border-white/10 items-center">
                    <ActivityIndicator size="large" color="#0d7ff2" />
                    <Text className="text-white font-bold text-lg mt-4 mb-1">OBD 연결 중</Text>
                    <Text className="text-text-dim text-sm text-center">블루투스 장치에 연결하고 있습니다...</Text>
                </View>
            </View>
        </Modal>
    );
}
