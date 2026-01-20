import React, { useState, useEffect } from 'react';
import {
    View,
    Text,
    TouchableOpacity,
    FlatList,
    Modal,
    ActivityIndicator,
    Alert,
} from 'react-native';
import { MaterialIcons } from '@expo/vector-icons';
import BleService, { Peripheral } from '../services/BleService';

interface ObdConnectProps {
    visible: boolean;
    onClose: () => void;
    onConnected?: (device: Peripheral) => void;
}

export default function ObdConnect({ visible, onClose, onConnected }: ObdConnectProps) {
    const [isScanning, setIsScanning] = useState(false);
    const [peripherals, setPeripherals] = useState<Map<string, Peripheral>>(new Map());
    const [connectedDeviceId, setConnectedDeviceId] = useState<string | null>(null);

    useEffect(() => {
        BleService.initialize();
    }, []);

    useEffect(() => {
        // Add listeners
        const discoverListener = BleService.addListener(
            'BleManagerDiscoverPeripheral',
            handleDiscoverPeripheral
        );
        const stopScanListener = BleService.addListener(
            'BleManagerStopScan',
            handleStopScan
        );

        return () => {
            discoverListener.remove();
            stopScanListener.remove();
        };
    }, []);

    const handleDiscoverPeripheral = (peripheral: Peripheral) => {
        // console.log('Discovered:', peripheral); 
        // if (!peripheral.name) return; // Filter unnamed devices
        // Show all devices for debugging
        if (!peripheral.name) peripheral.name = 'Unnamed Device';
        setPeripherals((map) => new Map(map.set(peripheral.id, peripheral)));
    };

    const handleStopScan = () => {
        setIsScanning(false);
    };

    const startScan = async () => {
        const hasPermission = await BleService.requestPermissions();
        if (!hasPermission) {
            Alert.alert('권한 필요', '블루투스 사용 권한이 필요합니다.');
            return;
        }

        setPeripherals(new Map());
        setIsScanning(true);
        try {
            await BleService.startScan(); // Scan for 5 seconds
        } catch (e) {
            console.error(e);
            setIsScanning(false);
        }
    };

    const connectToDevice = async (peripheral: Peripheral) => {
        try {
            await BleService.stopScan();
            setIsScanning(false);

            // Show loading indicator logic here if needed
            await BleService.connect(peripheral.id);
            setConnectedDeviceId(peripheral.id);

            // Need to retrieve services after connecting
            await BleService.retrieveServices(peripheral.id);

            Alert.alert('연결 성공', `${peripheral.name}에 연결되었습니다.`);
            if (onConnected) onConnected(peripheral);
            onClose();
        } catch (error) {
            Alert.alert('연결 실패', `기기에 연결할 수 없습니다.\n오류: ${error}`);
            console.error(error);
        }
    };

    const renderItem = ({ item }: { item: Peripheral }) => (
        <TouchableOpacity
            className="bg-[#1e2936] p-4 mb-2 rounded-xl flex-row items-center justify-between border border-white/5 active:bg-[#1e2936]/80"
            onPress={() => connectToDevice(item)}
        >
            <View>
                <Text className="text-white font-bold text-base">{item.name}</Text>
                <Text className="text-slate-400 text-xs">{item.id}</Text>
            </View>
            <View className="flex-row items-center gap-2">
                <Text className="text-slate-500 text-xs">RSSI: {item.rssi}</Text>
                <MaterialIcons name="bluetooth" size={20} color="#0d7ff2" />
            </View>
        </TouchableOpacity>
    );

    return (
        <Modal visible={visible} animationType="slide" transparent>
            <View className="flex-1 bg-black/80 justify-end">
                <View className="bg-[#101922] h-[70%] rounded-t-3xl p-6 border-t border-white/10">
                    <View className="flex-row justify-between items-center mb-6">
                        <Text className="text-white text-xl font-bold">OBD 스캐너 연결</Text>
                        <TouchableOpacity onPress={onClose} className="p-2 bg-[#1e2936] rounded-full">
                            <MaterialIcons name="close" size={20} color="white" />
                        </TouchableOpacity>
                    </View>

                    <View className="flex-row gap-3 mb-6">
                        <TouchableOpacity
                            onPress={startScan}
                            disabled={isScanning}
                            className={`flex-1 py-4 rounded-xl items-center justify-center border ${isScanning ? 'bg-transparent border-[#0d7ff2]' : 'bg-[#0d7ff2] border-[#0d7ff2]'}`}
                        >
                            {isScanning ? (
                                <View className="flex-row items-center gap-2">
                                    <ActivityIndicator color="#0d7ff2" size="small" />
                                    <Text className="text-[#0d7ff2] font-bold">검색 중...</Text>
                                </View>
                            ) : (
                                <Text className="text-white font-bold text-base">기기 검색 시작</Text>
                            )}
                        </TouchableOpacity>
                    </View>

                    <FlatList
                        data={Array.from(peripherals.values())}
                        renderItem={renderItem}
                        keyExtractor={(item) => item.id}
                        ListEmptyComponent={() => (
                            <View className="items-center justify-center py-10">
                                <MaterialIcons name="bluetooth-searching" size={48} color="#334155" />
                                <Text className="text-slate-500 mt-4 text-center">검색된 기기가 없습니다.{'\n'}스캔 버튼을 눌러주세요.</Text>
                            </View>
                        )}
                    />
                </View>
            </View>
        </Modal>
    );
}
