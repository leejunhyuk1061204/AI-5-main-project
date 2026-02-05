# 주행 이력 무한 스크롤 구현 가이드

이 문서는 `DrivingHis.tsx`의 주행 이력 리스트를 무한 스크롤 방식으로 개선하기 위한 가이드입니다.

## 1. 구현 목표
- 기존 5개 고정 노출 방식에서 스크롤 시 5개씩 추가 로드되는 방식으로 변경
- `FlatList`를 사용하여 대량 데이터 렌더링 최적화
- 상단 점수 및 그래프 섹션을 `ListHeaderComponent`로 통합

## 2. 주요 변경 사항

### A. 상태 관리 추가
`DrivingHis.tsx` 상단에 현재 표시할 아이템 개수를 관리하는 상태를 추가합니다.
```typescript
const [displayCount, setDisplayCount] = useState(5);
```

### B. 추가 로드 로직
스크롤이 끝에 도달했을 때 호출될 함수를 작성합니다.
```typescript
const loadMore = () => {
    if (displayCount < trips.length) {
        setDisplayCount(prev => prev + 5);
    }
};
```

### C. UI 구조 개편 (FlatList 도입)
기존 `ScrollView`를 `FlatList`로 교체합니다.

```tsx
<FlatList
    data={trips.slice(0, displayCount)}
    keyExtractor={(item, index) => index.toString()}
    renderItem={({ item: trip }) => (
        // 기존 주행 기록 카드 컴포넌트 렌더링
    )}
    ListHeaderComponent={() => (
        // 기존 ScrollView 내부의 상단 점수판 및 그래프 섹션
    )}
    onEndReached={loadMore}
    onEndReachedThreshold={0.5}
    contentContainerStyle={{ padding: 16 }}
/>
```

## 3. 작업 시 주의사항
- **상단 섹션 이동**: `FlatList` 사용 시 `ScrollView` 안에 `FlatList`를 넣으면 경고가 발생하므로, 반드시 상단 UI를 `ListHeaderComponent` 속성으로 넘겨주어야 합니다.
- **성능**: `slice`를 사용하여 클라이언트 측에서 처리하므로 현재 데이터 양(8~10개)에서는 무리가 없지만, 데이터가 매우 많아질 경우 서버 측 페이지네이션(`offset`, `limit` API 파라미터) 도입이 필요합니다.
