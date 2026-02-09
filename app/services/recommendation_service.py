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
            "Backpack (appropriate size)",
            "Water bottles/hydration system",
            "First aid kit",
            "Map and compass/GPS",
            "Headlamp with extra batteries",
            "Sun protection (sunscreen, sunglasses, hat)",
            "Emergency whistle",
            "Knife or multi-tool"
        ]

        # Add navigation
        if route.difficulty in [TrailDifficulty.DIFFICULT, TrailDifficulty.EXPERT]:
            essential_items.extend([
                "GPS device or smartphone with offline maps",
                "Emergency shelter/bivy"
            ])

        recommendations.append(
            EquipmentRecommendation(category="essential", items=essential_items)
        )

        # Multi-day specific items
        if multi_day_plan and multi_day_plan.total_days > 1:
            overnight_items = [
                "Sleeping bag (appropriate temperature rating)",
                "Sleeping pad",
                "Tent or shelter",
                "Cooking system (stove, fuel, pot)",
                "Food storage bag/bear canister",
                "Toiletries and toilet paper",
                "Water purification (filter or tablets)"
            ]

            # Check if huts are available
            has_huts = any(
                stop.node_type.value == 'hut'
                for stop in multi_day_plan.overnight_stops
            )

            if has_huts:
                overnight_items.append("Hut sleeping bag liner (huts often provide blankets)")
            else:
                overnight_items.append("Full camping setup required (no huts)")

            recommendations.append(
                EquipmentRecommendation(category="overnight", items=overnight_items)
            )

        # Clothing recommendations
        clothing_items = [
            "Moisture-wicking base layers",
            "Insulating mid-layer (fleece/down)",
            "Waterproof rain jacket",
            "Hiking pants/shorts",
            "Hiking boots/shoes (broken in)",
            "Extra socks (wool or synthetic)",
            "Warm hat and gloves"
        ]

        if season == "winter" or route.waypoints and any(w.elevation > 3000 for w in route.waypoints):
            clothing_items.extend([
                "Insulated jacket",
                "Waterproof pants",
                "Winter hat and gloves",
                "Gaiters"
            ])

        recommendations.append(
            EquipmentRecommendation(category="clothing", items=clothing_items)
        )

        # Difficulty-based recommendations
        if route.difficulty in [TrailDifficulty.DIFFICULT, TrailDifficulty.EXPERT]:
            technical_items = [
                "Trekking poles",
                "Gaiters",
                "Microspikes or crampons (if icy conditions)",
                "Helmet (for exposed/rocky terrain)",
                "Rope and harness (if scrambling/via ferrata)"
            ]

            recommendations.append(
                EquipmentRecommendation(category="technical", items=technical_items)
            )

        # Optional comfort items
        optional_items = [
            "Camera",
            "Trekking poles (if not already listed)",
            "Insect repellent",
            "Portable battery pack",
            "Book or entertainment",
            "Repair kit (duct tape, cord, patches)"
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
            f"Plan for {total_days} day(s) of hiking",
            f"Estimated {daily_calories} kcal needed per day",
            "Pack high-calorie, lightweight foods (dried fruits, nuts, energy bars)"
        ]

        if multi_day_plan and multi_day_plan.total_days > 1:
            notes.extend([
                "Include freeze-dried meals for dinners",
                "Pack extra snacks for energy throughout the day",
                "Consider resupply points if available"
            ])

            # Check for water sources
            has_water_sources = any(
                'water' in stop.amenities
                for stop in multi_day_plan.overnight_stops
            )

            if has_water_sources:
                notes.append("Water sources available at overnight stops - bring purification method")
            else:
                notes.append("Limited water sources - plan to carry enough water between stops")

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
