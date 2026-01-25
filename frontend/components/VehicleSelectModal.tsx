import React, { useState, useEffect } from 'react';
import { View, Text, TouchableOpacity, ScrollView, Modal, Pressable, ActivityIndicator } from 'react-native';
import { useAlertStore } from '../store/useAlertStore';
import { MaterialIcons } from '@expo/vector-icons';
import { getVehicleList, VehicleResponse, setPrimaryVehicle as apiSetPrimaryVehicle } from '../api/vehicleApi';

interface VehicleSelectModalProps {
    visible: boolean;
    onClose: () => void;
    onSelect: (vehicle: VehicleResponse) => void;
    title?: string;
    description?: string;
}

export default function VehicleSelectModal({
    visible,
    onClose,
    onSelect,
    title = "차량 선택",
    description = "진단을 진행할 차량을 선택해주세요."
}: VehicleSelectModalProps) {
    const [vehicles, setVehicles] = useState<VehicleResponse[]>([]);
    const [selectedVehicleId, setSelectedVehicleId] = useState<number | null>(null); // For UI indication if needed
    const [isLoading, setIsLoading] = useState(false);

    // Load vehicles when modal becomes visible
    useEffect(() => {
        if (visible) {
            loadVehicles();
        }
    }, [visible]);

    const loadVehicles = async () => {
        try {
            setIsLoading(true);
            const list = await getVehicleList();

            // 정렬 로직: 대표 차량을 맨 위로, 나머지는 등록 순서(API 반환 순서)대로
            const sortedList = [...list].sort((a, b) => {
                if (a.isPrimary) return -1;
                if (b.isPrimary) return 1;
                return 0; // 등록 순서 유지 (stable sort)
            });

            setVehicles(sortedList);

            // Optional: Pre-select primary vehicle if none selected? 
            // For now, let's just let user choose.
        } catch (error) {
            console.error('[VehicleSelectModal] Failed to load vehicles:', error);
            useAlertStore.getState().showAlert('오류', '차량 목록을 불러오는데 실패했습니다.', 'ERROR');
        } finally {
            setIsLoading(false);
        }
    };

    const handleSelect = (vehicle: VehicleResponse) => {
        onSelect(vehicle);
        onClose();
    };

    return (
        <Modal
            animationType="fade"
            transparent={true}
            visible={visible}
            onRequestClose={onClose}
        >
            <Pressable
                className="flex-1 bg-black/70 justify-center items-center px-6"
                onPress={onClose}
            >
                <Pressable
                    className="w-full bg-[#1a1e23] border border-white/10 rounded-3xl overflow-hidden"
                    onPress={(e) => e.stopPropagation()}
                >
                    {/* Header */}
                    <View className="px-6 py-5 border-b border-white/10 flex-row items-center justify-between">
                        <Text className="text-lg font-bold text-white">{title}</Text>
                        <TouchableOpacity
                            className="w-8 h-8 items-center justify-center rounded-full bg-white/5 active:bg-white/10"
                            onPress={onClose}
                        >
                            <MaterialIcons name="close" size={20} color="#94a3b8" />
                        </TouchableOpacity>
                    </View>

                    {/* Content */}
                    <View className="max-h-80 min-h-[150px] justify-center">
                        {isLoading ? (
                            <ActivityIndicator size="large" color="#0d7ff2" />
                        ) : vehicles.length === 0 ? (
                            <View className="p-8 items-center">
                                <MaterialIcons name="directions-car" size={48} color="#475569" />
                                <Text className="text-slate-400 mt-4 text-center">
                                    등록된 차량이 없습니다.
                                </Text>
                            </View>
                        ) : (
                            <ScrollView>
                                {vehicles.map((vehicle, index) => {
                                    const isLast = index === vehicles.length - 1;
                                    return (
                                        <TouchableOpacity
                                            key={vehicle.vehicleId}
                                            className={`flex-row items-center gap-4 px-6 py-4 active:bg-white/5 ${!isLast ? 'border-b border-white/5' : ''}`}
                                            onPress={() => handleSelect(vehicle)}
                                        >
                                            {/* Vehicle Icon */}
                                            <View className="w-12 h-12 items-center justify-center rounded-xl bg-white/5 border border-white/10">
                                                <MaterialIcons
                                                    name="directions-car"
                                                    size={24}
                                                    color="#94a3b8"
                                                />
                                            </View>

                                            {/* Vehicle Info */}
                                            <View className="flex-1">
                                                <Text className="text-base font-semibold text-white mb-0.5">
                                                    {vehicle.manufacturer} {vehicle.modelName}
                                                </Text>
                                                <Text className="text-slate-500 text-xs">
                                                    {vehicle.carNumber || '번호판 미등록'}
                                                </Text>
                                            </View>

                                            <MaterialIcons name="chevron-right" size={24} color="#475569" />
                                        </TouchableOpacity>
                                    );
                                })}
                            </ScrollView>
                        )}
                    </View>

                    {/* Footer */}
                    <View className="px-6 py-4 border-t border-white/10">
                        <Text className="text-xs text-slate-500 text-center">
                            {description}
                        </Text>
                    </View>
                </Pressable>
            </Pressable>
        </Modal>
    );
}
