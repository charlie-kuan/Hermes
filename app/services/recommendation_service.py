"""Equipment and food recommendation service."""

from typing import List

from loguru import logger

from app.models.domain import (
    EquipmentRecommendation,
    FoodRecommendation,
    MultiDayPlan,
    Route,
    TrailDifficulty
)


class RecommendationService:
    """Provides equipment and food recommendations based on route characteristics."""

    def __init__(self):
        pass

    def recommend_equipment(
        self,
        route: Route,
        multi_day_plan: MultiDayPlan = None,
        season: str = "summer"
    ) -> List[EquipmentRecommendation]:
        """
        Generate equipment recommendations for a route.

        Args:
            route: Route to recommend equipment for
            multi_day_plan: Optional multi-day plan
            season: Season (summer, winter, spring, fall)

        Returns:
            List of equipment recommendations by category
        """
        recommendations = []

        # Essential items (always needed)
        essential_items = [
            "適合尺寸的背包",
            "水瓶或水袋系統",
            "急救包",
            "地圖與指北針/GPS",
            "頭燈與備用電池",
            "防曬用品（防曬乳、太陽眼鏡、帽子）",
            "緊急哨子",
            "刀具或多功能工具"
        ]

        # Add navigation
        if route.difficulty in [TrailDifficulty.DIFFICULT, TrailDifficulty.EXPERT]:
            essential_items.extend([
                "GPS裝置或具離線地圖的智慧型手機",
                "緊急庇護所/露宿袋"
            ])

        recommendations.append(
            EquipmentRecommendation(category="essential", items=essential_items)
        )

        # Multi-day specific items
        if multi_day_plan and multi_day_plan.total_days > 1:
            overnight_items = [
                "適合溫度等級的睡袋",
                "睡墊",
                "帳篷或遮蔽物",
                "炊煮系統（爐具、燃料、鍋具）",
                "食物收納袋/防熊罐",
                "盥洗用具與衛生紙",
                "淨水設備（濾水器或淨水錠）"
            ]

            # Check if huts are available
            has_huts = any(
                stop.node_type.value == 'hut'
                for stop in multi_day_plan.overnight_stops
            )

            if has_huts:
                overnight_items.append("山屋睡袋內袋（山屋通常提供毛毯）")
            else:
                overnight_items.append("需完整露營裝備（無山屋）")

            recommendations.append(
                EquipmentRecommendation(category="overnight", items=overnight_items)
            )

        # Clothing recommendations
        clothing_items = [
            "排汗快乾底層衣物",
            "保暖中層（刷毛/羽絨）",
            "防水雨衣",
            "登山長褲/短褲",
            "已磨合的登山鞋/健行鞋",
            "備用襪子（羊毛或合成纖維）",
            "保暖帽與手套"
        ]

        if season == "winter" or route.waypoints and any(w.elevation > 3000 for w in route.waypoints):
            clothing_items.extend([
                "保暖外套",
                "防水長褲",
                "冬季保暖帽與手套",
                "綁腿"
            ])

        recommendations.append(
            EquipmentRecommendation(category="clothing", items=clothing_items)
        )

        # Difficulty-based recommendations
        if route.difficulty in [TrailDifficulty.DIFFICULT, TrailDifficulty.EXPERT]:
            technical_items = [
                "登山杖",
                "綁腿",
                "簡易冰爪或冰爪（結冰路況）",
                "安全頭盔（裸岩或碎石地形）",
                "繩索與吊帶（攀岩路段/鐵線橋）"
            ]

            recommendations.append(
                EquipmentRecommendation(category="technical", items=technical_items)
            )

        # Optional comfort items
        optional_items = [
            "相機",
            "登山杖（若尚未列入）",
            "防蟲液",
            "行動電源",
            "書籍或娛樂用品",
            "修補工具包（膠帶、繩索、補丁）"
        ]

        recommendations.append(
            EquipmentRecommendation(category="optional", items=optional_items)
        )

        logger.info(f"Generated {len(recommendations)} equipment recommendation categories")

        return recommendations

    def recommend_food(
        self,
        route: Route,
        multi_day_plan: MultiDayPlan = None,
        fitness_level: str = "moderate",
        pack_weight_kg: float = 12.0
    ) -> FoodRecommendation:
        """
        Generate food and water recommendations.

        Args:
            route: Route to plan food for
            multi_day_plan: Optional multi-day plan
            fitness_level: Hiker fitness level
            pack_weight_kg: Pack weight

        Returns:
            FoodRecommendation with calorie and water needs
        """
        # Calculate calories burned per day
        from app.core.time_estimators import TimeEstimator
        time_estimator = TimeEstimator()

        if multi_day_plan:
            # Multi-day route
            total_days = multi_day_plan.total_days

            # Calculate average calories per day
            total_calories = time_estimator.estimate_calories_burned(
                route.total_distance,
                route.total_elevation_gain,
                pack_weight_kg
            )

            daily_calories = int(total_calories / max(1, total_days))

        else:
            # Single day
            total_days = 1
            daily_calories = time_estimator.estimate_calories_burned(
                route.total_distance,
                route.total_elevation_gain,
                pack_weight_kg
            )
            total_calories = daily_calories

        # Adjust for difficulty and effort
        if route.difficulty == TrailDifficulty.EXPERT:
            daily_calories = int(daily_calories * 1.2)
        elif route.difficulty == TrailDifficulty.DIFFICULT:
            daily_calories = int(daily_calories * 1.1)

        # Ensure minimum calories
        daily_calories = max(2200, min(4500, daily_calories))
        total_calories = daily_calories * total_days

        # Calculate meals per day
        meals_per_day = 3 if total_days > 1 else 1

        # Calculate water needs
        base_water = 2.5  # liters per day

        # Adjust for effort
        if route.estimated_time > 6:
            base_water = 3.0
        if route.estimated_time > 8:
            base_water = 3.5

        # Adjust for elevation gain
        if route.total_elevation_gain > 1000:
            base_water += 0.5

        daily_water = round(base_water, 1)

        # Generate notes
        notes = [
            f"規劃 {total_days} 天的登山行程",
            f"每日預估需要 {daily_calories} 大卡熱量",
            "攜帶高熱量、輕量化食物（果乾、堅果、能量棒）"
        ]

        if multi_day_plan and multi_day_plan.total_days > 1:
            notes.extend([
                "準備冷凍乾燥餐包作為晚餐",
                "額外攜帶行動糧以補充體力",
                "考慮沿途補給點（如有）"
            ])

            # Check for water sources
            has_water_sources = any(
                'water' in stop.amenities
                for stop in multi_day_plan.overnight_stops
            )

            if has_water_sources:
                notes.append("過夜點有水源 - 請攜帶淨水設備")
            else:
                notes.append("水源有限 - 需規劃攜帶足夠水量")

        else:
            notes.append("Carry enough water for the entire hike or know water source locations")

        if route.difficulty in [TrailDifficulty.DIFFICULT, TrailDifficulty.EXPERT]:
            notes.append("High-intensity route - pack extra electrolyte supplements")

        recommendation = FoodRecommendation(
            daily_calories=daily_calories,
            total_calories=total_calories,
            meals_per_day=meals_per_day,
            daily_water_liters=daily_water,
            notes=notes
        )

        logger.info(
            f"Food recommendation: {daily_calories} kcal/day, "
            f"{daily_water}L water/day for {total_days} day(s)"
        )

        return recommendation

    def get_safety_checklist(self, route: Route) -> List[str]:
        """
        Generate safety checklist for a route.

        Args:
            route: Route to generate checklist for

        Returns:
            List of safety items to check
        """
        checklist = [
            "Check weather forecast",
            "Tell someone your route and expected return time",
            "Ensure phone is charged and bring backup battery",
            "Download offline maps",
            "Check trail conditions and closures"
        ]

        if route.difficulty in [TrailDifficulty.DIFFICULT, TrailDifficulty.EXPERT]:
            checklist.extend([
                "Verify you have appropriate technical skills",
                "Consider hiring a guide if unfamiliar with terrain",
                "Check avalanche/rockfall conditions if applicable",
                "Bring emergency communication device (satellite messenger)"
            ])

        if route.estimated_time > 8:
            checklist.append("Start early to ensure enough daylight")

        if route.waypoints and any(w.elevation > 3000 for w in route.waypoints):
            checklist.extend([
                "Be aware of altitude sickness symptoms",
                "Acclimatize properly if coming from low elevation"
            ])

        return checklist
