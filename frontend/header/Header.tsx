import React, { useEffect, useMemo } from 'react';
import { View, Text, TouchableOpacity } from 'react-native';
import { MaterialIcons } from '@expo/vector-icons';
import { useNavigation } from '@react-navigation/native';
import { useUserStore } from '../store/useUserStore';
import { useBleStore } from '../store/useBleStore';
import { useVehicleStore } from '../store/useVehicleStore';

/** 연결된 차량 한 줄 라벨 (예: E-Class (W214), 벤츠 E클래스) */
function getConnectedVehicleLabel(vehicle: { manufacturerKo: string; modelNameKo: string; modelNameEn?: string | null } | undefined): string {
    if (!vehicle) return '';
    if (vehicle.modelNameEn && vehicle.modelNameEn.trim()) {
        return `${vehicle.modelNameKo} (${vehicle.modelNameEn})`;
    }
    return `${vehicle.manufacturerKo} ${vehicle.modelNameKo}`;
}

interface HeaderProps {
    navigation?: any;
    title?: string;
}

export default function Header({ navigation: propNavigation, ...props }: HeaderProps) {
    const navigation = propNavigation || useNavigation<any>();
    const { nickname, membership, loadUser } = useUserStore();
    const { status, connectedVehicleId } = useBleStore();
    const { vehicles } = useVehicleStore();

    useEffect(() => {
        loadUser();
    }, []);

    const connectedVehicle = useMemo(
        () => (connectedVehicleId ? vehicles.find(v => v.vehicleId === connectedVehicleId) : undefined),
        [connectedVehicleId, vehicles]
    );
    const vehicleLabel = useMemo(() => getConnectedVehicleLabel(connectedVehicle), [connectedVehicle]);

    const getStatusInfo = () => {
        switch (status) {
            case 'connected':
                return {
                    text: vehicleLabel ? `${vehicleLabel} : Connected` : 'Connected',
                    color: 'text-success'
                };
            case 'connecting':
                return { text: 'Connecting...', color: 'text-warning' };
            default:
                return { text: 'Disconnected', color: 'text-gray-400' };
        }
    };

    const statusInfo = getStatusInfo();

    return (
        <View className="flex-row items-center justify-between px-6 py-4 pb-2 bg-transparent z-10">
            <View>
                {props.title ? (
                    <Text className="text-2xl font-bold text-white tracking-tight">
                        {props.title}
                    </Text>
                ) : nickname ? (
                    <View className="flex-row items-center gap-2">
                        <Text className="text-2xl font-bold text-primary tracking-tight">
                            {nickname}님
                        </Text>
                        {membership === 'BUSINESS' ? (
                            <View className="bg-premium/20 px-2 py-0.5 rounded-full border border-premium/40">
                                <Text className="text-premium text-[10px] font-bold">BUSINESS</Text>
                            </View>
                        ) : membership === 'PREMIUM' ? (
                            <View className="bg-primary/20 px-2 py-0.5 rounded-full border border-primary/40">
                                <Text className="text-primary text-[10px] font-bold">PREMIUM</Text>
                            </View>
                        ) : null}
                    </View>
                ) : (
                    <TouchableOpacity onPress={() => navigation.navigate('Login')}>
                        <Text className="text-2xl font-bold text-primary tracking-tight">
                            로그인
                        </Text>
                    </TouchableOpacity>
                )}
                <Text className={`text-xs mt-1 font-medium ${statusInfo.color}`} numberOfLines={1}>
                    {statusInfo.text}
                </Text>
            </View>
            <TouchableOpacity
                className="relative w-11 h-11 items-center justify-center rounded-xl bg-white/5 border border-white/10 active:bg-white/10"
                activeOpacity={0.7}
                onPress={() => navigation.navigate('AlertMain')}
            >
                <MaterialIcons name="notifications-none" size={22} color="#0d7ff2" />
                {/* Unread Badge - 읽지 않은 알림이 있을 때 표시 */}
                {/* <View className="absolute top-1.5 right-1.5 w-2 h-2 bg-error rounded-full border border-[#101922]" /> */}
            </TouchableOpacity>
        </View>
    );
}
