"use client";

import { Bar, BarChart, CartesianGrid, Line, LineChart, XAxis } from "recharts";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import {
  type ChartConfig,
  ChartContainer,
  ChartTooltip,
  ChartTooltipContent,
} from "@/components/ui/chart";
import type { RatingBucket, ReviewVolumePoint } from "@/lib/api";

function formatDay(value: unknown): string {
  const parsed = new Date(String(value));
  return Number.isNaN(parsed.getTime())
    ? ""
    : parsed.toLocaleDateString(undefined, { month: "short", day: "numeric" });
}

const volumeConfig: ChartConfig = {
  count: { label: "Reviews", color: "var(--chart-1)" },
};

export function ReviewVolumeChart({ data }: { data: ReviewVolumePoint[] }) {
  return (
    <Card>
      <CardHeader>
        <CardTitle>Review volume</CardTitle>
      </CardHeader>
      <CardContent>
        <ChartContainer config={volumeConfig} className="aspect-auto h-64 w-full">
          <LineChart data={data} margin={{ left: 12, right: 12 }}>
            <CartesianGrid vertical={false} />
            <XAxis
              dataKey="date"
              tickLine={false}
              axisLine={false}
              tickMargin={8}
              minTickGap={24}
              tickFormatter={formatDay}
            />
            <ChartTooltip content={<ChartTooltipContent labelFormatter={formatDay} />} />
            <Line
              dataKey="count"
              type="monotone"
              stroke="var(--color-count)"
              strokeWidth={2}
              dot={false}
            />
          </LineChart>
        </ChartContainer>
      </CardContent>
    </Card>
  );
}

const ratingConfig: ChartConfig = {
  count: { label: "Reviews", color: "var(--chart-2)" },
};

export function RatingDistributionChart({ data }: { data: RatingBucket[] }) {
  const chartData = data.map((d) => ({ ...d, label: `${d.rating}★` }));
  return (
    <Card>
      <CardHeader>
        <CardTitle>Rating distribution</CardTitle>
      </CardHeader>
      <CardContent>
        <ChartContainer config={ratingConfig} className="aspect-auto h-64 w-full">
          <BarChart data={chartData} margin={{ left: 12, right: 12 }}>
            <CartesianGrid vertical={false} />
            <XAxis dataKey="label" tickLine={false} axisLine={false} tickMargin={8} />
            <ChartTooltip content={<ChartTooltipContent />} />
            <Bar dataKey="count" fill="var(--color-count)" radius={4} />
          </BarChart>
        </ChartContainer>
      </CardContent>
    </Card>
  );
}
