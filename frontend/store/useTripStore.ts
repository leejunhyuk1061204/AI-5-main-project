import { create } from 'zustand';
import { persist, createJSONStorage } from 'zustand/middleware';
import AsyncStorage from '@react-native-async-storage/async-storage';
import tripApi from '../api/tripApi';

interface TripState {
    currentTripId: string | null;
    isDriving: boolean;
    startTime: string | null;
    vehicleId: string | null;

    // Actions
    startTrip: (vehicleId: string) => Promise<void>;
    endTrip: () => Promise<void>;
    reset: () => void;
}

export const useTripStore = create<TripState>()(
    persist(
        (set, get) => ({
            currentTripId: null,
            isDriving: false,
            startTime: null,
            vehicleId: null,

            startTrip: async (vehicleId: string) => {
                // 이미 주행 중이라면 무시 (또는 기존 세션 종료 후 재시작)
                if (get().isDriving && get().currentTripId) {
                    console.log('[TripStore] Already driving, skipping start');
                    return;
                }

                try {
                    console.log('[TripStore] Starting trip for vehicle:', vehicleId);
                    const response = await tripApi.startTrip(vehicleId);

                    if (response.success && response.data) {
                        set({
                            isDriving: true,
                            currentTripId: response.data.tripId,
                            startTime: response.data.startTime,
                            vehicleId: vehicleId
                        });
                        console.log('[TripStore] Trip started:', response.data.tripId);
                    }
                } catch (error) {
                    console.error('[TripStore] Failed to start trip:', error);
                    // 실패해도 주행 상태가 꼬이지 않도록 예외 처리
                }
            },

            endTrip: async () => {
                const { currentTripId } = get();
                if (!currentTripId) {
                    console.log('[TripStore] No active trip to end');
                    set({ isDriving: false, vehicleId: null, startTime: null });
                    return;
                }

                try {
                    console.log('[TripStore] Ending trip:', currentTripId);
                    await tripApi.endTrip(currentTripId);
                    console.log('[TripStore] Trip ended successfully');
                } catch (error) {
                    console.error('[TripStore] Failed to end trip:', error);
                } finally {
                    // 성공하든 실패하든 로컬 상태는 리셋
                    set({
                        isDriving: false,
                        currentTripId: null,
                        startTime: null,
                        vehicleId: null
                    });
                }
            },

            reset: () => {
                set({
                    isDriving: false,
                    currentTripId: null,
                    startTime: null,
                    vehicleId: null
                });
            }
        }),
        {
            name: 'trip-storage',
            storage: createJSONStorage(() => AsyncStorage),
        }
    )
);
