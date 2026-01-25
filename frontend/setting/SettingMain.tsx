import React from 'react';
import { View, Text, TouchableOpacity } from 'react-native';
import { MaterialIcons } from '@expo/vector-icons';
import { useNavigation } from '@react-navigation/native';
import Header from '../header/Header';
import AsyncStorage from '@react-native-async-storage/async-storage';
import BaseScreen from '../components/layout/BaseScreen';

export default function SettingMain() {
    const navigation = useNavigation<any>();
    const [nickname, setNickname] = React.useState<string>('사용자');

    React.useEffect(() => {
        const getNickname = async () => {
            const stored = await AsyncStorage.getItem('userNickname');
            if (stored) setNickname(stored);
        };
        const unsubscribe = navigation.addListener('focus', getNickname);
        return unsubscribe;
    }, [navigation]);

    const SectionTitle = ({ title }: { title: string }) => (
        <View className="px-2 mb-3 mt-2 flex-row items-center justify-between">
            <Text className="text-[13px] font-semibold text-gray-400">{title}</Text>
        </View>
    );

    const SettingsItem = ({ icon, title, subtitle, isLast, onPress }: { icon: keyof typeof MaterialIcons.glyphMap, title: string, subtitle?: string, isLast?: boolean, onPress?: () => void }) => (
        <TouchableOpacity
            className={`flex-row items-center gap-4 px-4 py-4 active:bg-white/5 ${!isLast ? 'border-b border-white/5' : ''}`}
            activeOpacity={0.7}
            onPress={onPress}
        >
            <View className="w-11 h-11 rounded-xl bg-primary/10 border border-primary/20 items-center justify-center shrink-0">
                <MaterialIcons name={icon} size={24} color="#0d7ff2" />
            </View>
            <View className="flex-1 justify-center">
                <Text className="text-white text-base font-medium leading-tight mb-0.5">{title}</Text>
                {subtitle && <Text className="text-gray-500 text-xs">{subtitle}</Text>}
            </View>
            <MaterialIcons name="chevron-right" size={24} color="#0d7ff2" />
        </TouchableOpacity>
    );

    return (
        <BaseScreen
            header={<Header />}
            padding={true}
            useBottomNav={true}
        >
            {/* Account Settings Section */}
            <View className="mb-6">
                <SectionTitle title="계정 설정" />
                <View className="bg-[#ffffff08] border border-[#ffffff14] rounded-2xl overflow-hidden">
                    <SettingsItem
                        icon="person"
                        title="내 프로필"
                        subtitle={`${nickname} • 프리미엄 멤버십`}
                        onPress={() => navigation.navigate('MyPage')}
                    />
                    <SettingsItem
                        icon="notifications-active"
                        title="알림 설정"
                        isLast
                        onPress={() => navigation.navigate('AlertSetting')}
                    />
                </View>
            </View>

            {/* Vehicle & Services Section */}
            <View className="mb-6">
                <SectionTitle title="차량 및 서비스" />
                <View className="bg-[#ffffff08] border border-[#ffffff14] rounded-2xl overflow-hidden">
                    <SettingsItem
                        icon="directions-car"
                        title="내 차량 관리"
                        subtitle="Genesis GV80 • 12가 3456"
                        onPress={() => navigation.navigate('CarManage')}
                    />
                    <SettingsItem
                        icon="cloud-sync"
                        title="클라우드 연동"
                        isLast
                        onPress={() => navigation.navigate('Cloud')}
                    />
                </View>
            </View>

            {/* Logout Button */}
            <TouchableOpacity
                className="w-full py-4 bg-[#ffffff08] border border-red-400/10 rounded-2xl flex-row items-center justify-center gap-2 mt-2 active:bg-red-400/10 mb-10"
                activeOpacity={0.7}
                onPress={async () => {
                    try {
                        await AsyncStorage.clear();
                        navigation.reset({
                            index: 0,
                            routes: [{ name: 'Login' }],
                        });
                    } catch (e) {
                        console.error('Logout failed', e);
                        navigation.navigate('Login');
                    }
                }}
            >
                <MaterialIcons name="logout" size={18} color="#ff6b6b" />
                <Text className="text-[#ff6b6b] font-semibold text-sm">로그아웃</Text>
            </TouchableOpacity>
        </BaseScreen>
    );
}
