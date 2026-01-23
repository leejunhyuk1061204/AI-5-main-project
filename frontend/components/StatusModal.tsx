import React from 'react';
import { View, Text, Modal, TouchableOpacity } from 'react-native';
import { MaterialIcons } from '@expo/vector-icons';

interface StatusModalProps {
    visible: boolean;
    status: 'idle' | 'success' | 'error';
    title?: string;
    message: string;
    onConfirm?: () => void;
    onRetry?: () => void;
    onClose: () => void;
}

export default function StatusModal({
    visible,
    status,
    title,
    message,
    onConfirm,
    onRetry,
    onClose
}: StatusModalProps) {
    if (status === 'idle') return null;

    return (
        <Modal
            visible={visible}
            animationType="slide"
            transparent={true}
            onRequestClose={onClose}
        >
            <View className="flex-1 bg-black/60 backdrop-blur-sm justify-end">
                <View className="bg-[#101922] h-[40%] rounded-t-[32px] p-6 border-t border-white/5 relative">
                    {/* Header */}
                    <View className="flex-row justify-between items-center mb-6 px-1">
                        <Text className="text-white text-xl font-bold tracking-tight">
                            {title || (status === 'success' ? '성공' : '오류')}
                        </Text>
                        <TouchableOpacity
                            onPress={onClose}
                            className="w-8 h-8 rounded-full bg-[#ffffff08] items-center justify-center border border-[#ffffff0d]"
                        >
                            <MaterialIcons name="close" size={18} color="#a1a1aa" />
                        </TouchableOpacity>
                    </View>

                    {/* Content based on Status */}
                    {status === 'success' ? (
                        <View className="flex-1 items-center justify-center pb-10">
                            <View className="w-24 h-24 rounded-full bg-[#0d7ff2]/10 items-center justify-center mb-6 border border-[#0d7ff2]/20">
                                <MaterialIcons name="check" size={48} color="#0d7ff2" />
                            </View>
                            <Text className="text-white text-2xl font-bold mb-2">
                                {title || '성공'}
                            </Text>
                            <Text className="text-slate-400 text-center mb-8">
                                {message}
                            </Text>
                            <TouchableOpacity
                                onPress={onConfirm || onClose}
                                className="w-full py-4 bg-[#0d7ff2] rounded-xl items-center justify-center shadow-lg shadow-blue-500/20"
                            >
                                <Text className="text-white font-bold text-lg">확인</Text>
                            </TouchableOpacity>
                        </View>
                    ) : (
                        <View className="flex-1 items-center justify-center pb-10">
                            <View className="w-24 h-24 rounded-full bg-red-500/10 items-center justify-center mb-6 border border-red-500/20">
                                <MaterialIcons name="error-outline" size={48} color="#ef4444" />
                            </View>
                            <Text className="text-white text-2xl font-bold mb-2">
                                {title || '오류'}
                            </Text>
                            <Text className="text-slate-400 text-center mb-6">
                                {message}
                            </Text>
                            <TouchableOpacity
                                onPress={onRetry || onClose}
                                className="w-full py-4 bg-[#ffffff08] rounded-xl border border-white/10 items-center justify-center"
                            >
                                <Text className="text-white font-medium text-lg">다시 시도</Text>
                            </TouchableOpacity>
                        </View>
                    )}
                </View>
            </View>
        </Modal>
    );
}
