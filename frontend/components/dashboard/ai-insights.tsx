import { Sparkles } from 'lucide-react'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card'
import { Badge } from '@/components/ui/badge'

export function AiInsights() {
  const insights = [
    'Revenue growth accelerated 38% YoY, driven by enterprise adoption in UK market.',
    'Customer acquisition cost remains stable while lifetime value increases 24%.',
    'Operating expenses grew slower than revenue, improving operating margins to 18%.',
    'Cash position supports 18+ months of operations at current burn rate.',
  ]

  return (
    <Card className="col-span-full">
      <CardHeader>
        <div className="flex items-center gap-2">
          <Sparkles className="h-5 w-5 text-emerald-600" />
          <div>
            <CardTitle>AI Board Insights</CardTitle>
            <CardDescription>AI-generated executive commentary</CardDescription>
          </div>
        </div>
      </CardHeader>
      <CardContent>
        <div className="space-y-3">
          {insights.map((insight, index) => (
            <div key={index} className="flex gap-3">
              <Badge className="mt-1 h-fit flex-shrink-0 bg-emerald-100 text-emerald-800 dark:bg-emerald-900/30 dark:text-emerald-400">
                {index + 1}
              </Badge>
              <p className="text-sm text-foreground leading-relaxed">{insight}</p>
            </div>
          ))}
        </div>
      </CardContent>
    </Card>
  )
}