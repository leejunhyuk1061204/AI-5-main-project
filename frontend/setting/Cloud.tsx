import React, { useState } from 'react';
import { View, Text, TouchableOpacity, ScrollView } from 'react-native';
import { SafeAreaView, useSafeAreaInsets } from 'react-native-safe-area-context';
import { StatusBar } from 'expo-status-bar';
import { MaterialIcons, MaterialCommunityIcons } from '@expo/vector-icons';
import { useNavigation } from '@react-navigation/native';

// 클라우드 서비스 데이터 타입
interface CloudService {
    id: string;
    name: string;
    subtitle: string;
    icon: keyof typeof MaterialIcons.glyphMap | keyof typeof MaterialCommunityIcons.glyphMap;
    iconType: 'material' | 'community';
    isConnected: boolean;
    isHighlighted?: boolean;
}

// 클라우드 서비스 목록 (추가 제조사 포함)
const initialCloudServices: CloudService[] = [
    {
        id: 'hyundai',
        name: '현대 블루링크',
        subtitle: 'Bluelink Connected',
        icon: 'directions-car',
        iconType: 'material',
        isConnected: false,
        isHighlighted: true,
    },
    {
        id: 'kia',
        name: '기아 커넥트',
        subtitle: 'Kia Connect',
        icon: 'directions-car',
        iconType: 'material',
        isConnected: false,
    },
    {
        id: 'genesis',
        name: '제네시스 커넥티드',
        subtitle: 'Genesis Connected Services',
        icon: 'directions-car',
        iconType: 'material',
        isConnected: false,
    },
    {
        id: 'tesla',
        name: '테슬라',
        subtitle: 'Tesla Account',
        icon: 'electric-car',
        iconType: 'material',
        isConnected: false,
    },
    {
        id: 'bmw',
        name: 'BMW 커넥티드 드라이브',
        subtitle: 'BMW Connected Drive',
        icon: 'car-sports',
        iconType: 'community',
        isConnected: false,
    },
    {
        id: 'mercedes',
        name: '메르세데스-벤츠',
        subtitle: 'Mercedes me connect',
        icon: 'car-estate',
        iconType: 'community',
        isConnected: false,
    },
    {
        id: 'volvo',
        name: '볼보 카스',
        subtitle: 'Volvo Cars',
        icon: 'car-side',
        iconType: 'community',
        isConnected: false,
    },
    {
        id: 'chevrolet',
        name: '쉐보레 마이쉐보레',
        subtitle: 'myChevrolet',
        icon: 'directions-car',
        iconType: 'material',
        isConnected: false,
    },
    {
        id: 'renault',
        name: '르노 마이르노',
        subtitle: 'MY Renault',
        icon: 'directions-car',
        iconType: 'material',
        isConnected: false,
    },
];

export default function Cloud() {
    const navigation = useNavigation<any>();
    const insets = useSafeAreaInsets();
    const [services, setServices] = useState<CloudService[]>(initialCloudServices);

    // 연동 토글 핸들러
    const handleToggleConnect = (id: string) => {
        setServices(prev =>
            prev.map(service =>
                service.id === id
                    ? { ...service, isConnected: !service.isConnected }
                    : service
            )
        );
    };

    // 서비스 카드 컴포넌트
    const ServiceCard = ({ service }: { service: CloudService }) => (
        <View
            className={`bg-[#ffffff08] border rounded-2xl p-4 flex-row items-center justify-between ${service.isHighlighted ? 'border-l-4 border-l-primary/50 border-t-[#ffffff0a] border-r-[#ffffff0a] border-b-[#ffffff0a]' : 'border-[#ffffff0a]'
                }`}
        >
            <View className="flex-row items-center gap-4 flex-1">
                {/* 아이콘 */}
                <View className="w-12 h-12 rounded-xl bg-white/5 border border-white/10 items-center justify-center">
                    {service.iconType === 'material' ? (
                        <MaterialIcons
                            name={service.icon as keyof typeof MaterialIcons.glyphMap}
                            size={24}
                            color="#94a3b8"
                        />
                    ) : (
                        <MaterialCommunityIcons
                            name={service.icon as keyof typeof MaterialCommunityIcons.glyphMap}
                            size={24}
                            color="#94a3b8"
                        />
                    )}
                </View>

                {/* 텍스트 */}
                <View className="flex-1">
                    <Text className="text-white text-base font-semibold mb-0.5">{service.name}</Text>
                    <Text className="text-slate-500 text-xs">{service.subtitle}</Text>
                </View>
            </View>

            {/* 연동 버튼 */}
            {service.isConnected ? (
                <TouchableOpacity
                    className="px-4 py-2 rounded-full bg-white/5 border border-white/10 flex-row items-center gap-1"
                    activeOpacity={0.7}
                    onPress={() => handleToggleConnect(service.id)}
                >
                    <MaterialIcons name="check" size={14} color="#94a3b8" />
                    <Text className="text-slate-400 text-xs font-bold">연동됨</Text>
                </TouchableOpacity>
            ) : (
                <TouchableOpacity
                    className="px-4 py-2 rounded-full bg-primary active:bg-primary-dark"
                    activeOpacity={0.8}
                    onPress={() => handleToggleConnect(service.id)}
                >
                    <Text className="text-white text-xs font-bold">연동하기</Text>
                </TouchableOpacity>
            )}
        </View>
    );

    return (
        <View className="flex-1 bg-background-dark">
            <StatusBar style="light" />

            {/* 헤더 */}
            <View
                className="bg-background-dark/80 border-b border-white/5 px-4 py-4 flex-row items-center"
                style={{ paddingTop: insets.top + 8 }}
            >
                <TouchableOpacity
                    className="p-2 -ml-2 rounded-full active:bg-white/5"
                    onPress={() => navigation.goBack()}
                >
                    <MaterialIcons name="arrow-back-ios" size={22} color="#f1f5f9" />
                </TouchableOpacity>
                <Text className="flex-1 text-center text-lg font-bold text-slate-100 mr-8">
                    클라우드 연동
                </Text>
            </View>

            <ScrollView
                className="flex-1"
                contentContainerStyle={{ padding: 24, paddingBottom: 40 }}
                showsVerticalScrollIndicator={false}
            >
                {/* 타이틀 섹션 */}
                <View className="mb-8">
                    <Text className="text-xl font-bold text-slate-100 leading-8 mb-2">
                        제조사 계정을 연동하여{'\n'}실시간 차량 데이터를 받아보세요
                    </Text>
                    <Text className="text-sm text-slate-400 leading-relaxed">
                        연동 후 AI가 더욱 정확한 소모품 교체 시점을 예측해 드립니다.
                    </Text>
                </View>

                {/* 서비스 카드 목록 */}
                <View className="gap-4 mb-6">
                    {services.map(service => (
                        <ServiceCard key={service.id} service={service} />
                    ))}
                </View>

                {/* 보안 안내 */}
                <View className="p-4 rounded-xl bg-white/5 border border-white/5 flex-row items-start gap-3">
                    <MaterialIcons name="verified-user" size={18} color="#0d7ff2" style={{ marginTop: 2 }} />
                    <Text className="flex-1 text-xs text-slate-400 leading-relaxed">
                        데이터는 <Text className="text-slate-200 font-medium">AES-256</Text> 방식으로 안전하게 암호화됩니다.
                        차량 제조사의 인증 서버를 통해 직접 로그인하며, 사용자의 비밀번호는 저장되지 않습니다.
                    </Text>
                </View>
            </ScrollView>
        </View>
    );
}
