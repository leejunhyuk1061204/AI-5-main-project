import React, { useState, useEffect, useCallback } from 'react';
import { View, Text, TouchableOpacity, Image, FlatList, Modal, ActivityIndicator, Dimensions, StyleSheet } from 'react-native';
import { SafeAreaView } from 'react-native-safe-area-context';
import { StatusBar } from 'expo-status-bar';
import { MaterialIcons } from '@expo/vector-icons';
import { useNavigation, useRoute } from '@react-navigation/native';
import AsyncStorage from '@react-native-async-storage/async-storage';
import ocrApi, { MaintenanceHistoryResponse, FuelingHistoryResponse } from '../api/ocrApi';
import { BASE_URL as API_URL } from '../api/axios';

const { width } = Dimensions.get('window');
const COLUMN_COUNT = 3;
const ITEM_SIZE = width / COLUMN_COUNT;

interface GalleryItem {
    id: string;
    receiptId: string | null;
    imageUrl: string | null; // URL or local URI if available
    date: string;
    type: 'MAINTENANCE' | 'FUELING';
    title: string;
    cost: number;
}

export default function ReceiptGallery() {
    const navigation = useNavigation();
    const route = useRoute<any>();
    const vehicleId = route.params?.vehicleId;

    const [items, setItems] = useState<GalleryItem[]>([]);
    const [loading, setLoading] = useState(true);
    const [selectedImage, setSelectedImage] = useState<string | null>(null);

    const loadReceipts = async () => {
        if (!vehicleId) return;
        setLoading(true);
        try {
            const [maintenance, fueling] = await Promise.all([
                ocrApi.getMaintenanceHistory(vehicleId),
                ocrApi.getFuelingHistory(vehicleId)
            ]);

            const galleryItems: GalleryItem[] = [];

            // 정비 이력에서 영수증 추출
            maintenance.forEach((m: MaintenanceHistoryResponse) => {
                // receiptId가 있고, ocrData가 있는 경우에만 갤러리에 표시 (수동 입력 제외)
                if (m.receiptId && m.ocrData) {
                    // TODO: 실제 이미지 URL 경로 확인 필요. 임시로 receiptId 기반 URL 생성 로직 가정
                    // 만약 백엔드에서 이미지 URL을 별도 필드로 준다면 그것을 사용
                    // 여기서는 receiptId가 있으면 이미지가 있다고 가정하고 상세 보기 시 로드 시도
                    galleryItems.push({
                        id: `M-${m.id}`,
                        receiptId: m.receiptId,
                        imageUrl: null, // 상세 보기에서 로드
                        date: m.maintenanceDate,
                        type: 'MAINTENANCE',
                        title: m.itemDescription,
                        cost: m.cost || 0
                    });
                }
            });

            // 주유 이력에서 영수증 추출 (주유는 현재 수동 입력 위주라 receiptId가 없을 수 있음)
            fueling.forEach((f: FuelingHistoryResponse) => {
                if (f.receiptId) {
                    galleryItems.push({
                        id: `F-${f.id}`,
                        receiptId: f.receiptId,
                        imageUrl: null,
                        date: f.fuelingDate,
                        type: 'FUELING',
                        title: '주유',
                        cost: f.totalCost
                    });
                }
            });

            // 날짜순 정렬
            galleryItems.sort((a, b) => new Date(b.date).getTime() - new Date(a.date).getTime());
            setItems(galleryItems);

        } catch (error) {
            console.error('Failed to load receipts:', error);
        } finally {
            setLoading(false);
        }
    };

    useEffect(() => {
        loadReceipts();
    }, [vehicleId]);

    // 개별 아이템 컴포넌트 (Hooks 사용을 위해 분리)
    const ReceiptItem = React.memo(({ item, size, onPress }: { item: GalleryItem, size: number, onPress: (id: string | null) => void }) => {
        const [isValid, setIsValid] = useState(true);

        if (!isValid) return null;

        return (
            <TouchableOpacity
                style={{ width: size, height: size, padding: 1 }}
                onPress={() => onPress(item.receiptId)}
            >
                <View className="flex-1 bg-white/5 border border-white/10 overflow-hidden relative">
                    <Image
                        source={{
                            uri: `${API_URL}/api/v1/master/receipts/${item.receiptId}`,
                        }}
                        style={styles.image}
                        resizeMode="cover"
                        resizeMethod="resize"
                        onError={(e) => {
                            console.log(`Image load failed for ${item.receiptId}:`, e.nativeEvent.error);
                            setIsValid(false);
                        }}
                    />
                    {/* ... (오버레이 등 동일) ... */}
                    <View className="absolute bottom-0 left-0 right-0 bg-black/60 p-1">
                        <Text className="text-white text-[10px] text-center">{item.date}</Text>
                        <Text className="text-gray-300 text-[9px] text-center" numberOfLines={1}>{item.title}</Text>
                    </View>

                    <View className={`absolute top-1 right-1 w-2 h-2 rounded-full ${item.type === 'MAINTENANCE' ? 'bg-primary' : 'bg-orange-500'}`} />
                </View>
            </TouchableOpacity>
        );
    });

    const styles = StyleSheet.create({
        image: {
            ...StyleSheet.absoluteFillObject,
        },
    });

    const renderItem = useCallback(({ item }: { item: GalleryItem }) => {
        return (
            <ReceiptItem
                item={item}
                size={ITEM_SIZE}
                onPress={setSelectedImage}
            />
        );
    }, []);

    return (
        <SafeAreaView className="flex-1 bg-background-dark">
            <StatusBar style="light" />

            {/* Header */}
            <View className="flex-row items-center justify-between px-4 py-3 border-b border-white/5">
                <TouchableOpacity
                    onPress={() => navigation.goBack()}
                    className="w-10 h-10 items-center justify-center rounded-full active:bg-white/10"
                >
                    <MaterialIcons name="arrow-back-ios" size={20} color="white" />
                </TouchableOpacity>
                <Text className="text-white text-lg font-bold">영수증 갤러리</Text>
                <View className="w-10" />
            </View>

            {loading ? (
                <View className="flex-1 items-center justify-center">
                    <ActivityIndicator size="large" color="#0d7ff2" />
                </View>
            ) : items.length === 0 ? (
                <View className="flex-1 items-center justify-center">
                    <MaterialIcons name="receipt-long" size={48} color="#334155" />
                    <Text className="text-gray-500 text-sm mt-4">등록된 영수증이 없습니다.</Text>
                </View>
            ) : (
                <FlatList
                    data={items}
                    renderItem={renderItem}
                    keyExtractor={item => item.id}
                    numColumns={COLUMN_COUNT}
                    contentContainerStyle={{ paddingBottom: 20 }}
                />
            )}

            {/* Full Screen Modal */}
            <Modal
                visible={!!selectedImage}
                transparent={true}
                onRequestClose={() => setSelectedImage(null)}
                animationType="fade"
            >
                <View className="flex-1 bg-black justify-center items-center relative">
                    <TouchableOpacity
                        className="absolute top-12 right-6 z-10 p-2 bg-black/40 rounded-full"
                        onPress={() => setSelectedImage(null)}
                    >
                        <MaterialIcons name="close" size={30} color="white" />
                    </TouchableOpacity>

                    {selectedImage && (
                        <Image
                            source={{ uri: `${API_URL}/api/v1/master/receipts/${selectedImage}` }}
                            className="w-full h-full"
                            resizeMode="contain"
                            resizeMethod="resize"
                        />
                    )}
                </View>
            </Modal>
        </SafeAreaView>
    );
}
