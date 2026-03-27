import React, { useState } from 'react';
import {
  Eye,
  Globe,
  Code,
  Image as ImageIcon,
  FileText,
  Clock,
  ExternalLink,
  ChevronDown,
  ChevronUp,
  Maximize2,
} from 'lucide-react';
import { Card, CardHeader, CardContent } from '@/components/ui/Card';
import { Button } from '@/components/ui/Button';
import { Badge } from '@/components/ui/Badge';
import { useCurrentEpisode, useEpisodeState } from '@/hooks/useEpisode';
import { formatTimestamp, truncateText } from '@/utils/helpers';
import type { DOMElement } from '@/types';

interface ObservationViewProps {
  className?: string;
}

const DOMTree: React.FC<{ elements: DOMElement[]; depth?: number }> = ({
  elements,
  depth = 0,
}) => {
  const [expanded, setExpanded] = useState<Set<number>>(new Set([0, 1, 2]));

  const toggleExpand = (index: number) => {
    setExpanded((prev) => {
      const next = new Set(prev);
      if (next.has(index)) {
        next.delete(index);
      } else {
        next.add(index);
      }
      return next;
    });
  };

  if (depth > 3) return null;

  return (
    <div className="space-y-1">
      {elements.slice(0, 10).map((el, i) => {
        const hasChildren = el.children && el.children.length > 0;
        const isExpanded = expanded.has(i);

        return (
          <div key={i} style={{ paddingLeft: `${depth * 12}px` }}>
            <div className="flex items-center gap-1 text-xs font-mono hover:bg-dark-700/50 rounded px-1">
              {hasChildren && (
                <button
                  onClick={() => toggleExpand(i)}
                  className="text-dark-500 hover:text-dark-300"
                >
                  {isExpanded ? (
                    <ChevronDown className="w-3 h-3" />
                  ) : (
                    <ChevronUp className="w-3 h-3" />
                  )}
                </button>
              )}
              {!hasChildren && <span className="w-3" />}
              <span className="text-purple-400">&lt;{el.tag}</span>
              {el.id && (
                <span className="text-yellow-400">#{el.id}</span>
              )}
              {el.classes.length > 0 && (
                <span className="text-green-400">
                  .{el.classes.slice(0, 2).join('.')}
                </span>
              )}
              <span className="text-purple-400">&gt;</span>
              {el.text && (
                <span className="text-dark-400 truncate max-w-[100px]">
                  {truncateText(el.text, 20)}
                </span>
              )}
            </div>
            {hasChildren && isExpanded && (
              <DOMTree elements={el.children!} depth={depth + 1} />
            )}
          </div>
        );
      })}
      {elements.length > 10 && (
        <div
          className="text-xs text-dark-500 italic"
          style={{ paddingLeft: `${depth * 12}px` }}
        >
          +{elements.length - 10} more elements
        </div>
      )}
    </div>
  );
};

export const ObservationView: React.FC<ObservationViewProps> = ({
  className,
}) => {
  const { data: episode } = useCurrentEpisode();
  const { data: state, isLoading } = useEpisodeState(episode?.id);
  const [activeTab, setActiveTab] = useState<'page' | 'dom' | 'data' | 'screenshot'>('page');
  const [showFullScreen, setShowFullScreen] = useState(false);

  const observation = state?.observation;

  const tabs = [
    { key: 'page' as const, label: 'Page', icon: <Globe className="w-3 h-3" /> },
    { key: 'dom' as const, label: 'DOM', icon: <Code className="w-3 h-3" /> },
    { key: 'data' as const, label: 'Data', icon: <FileText className="w-3 h-3" /> },
    { key: 'screenshot' as const, label: 'Screenshot', icon: <ImageIcon className="w-3 h-3" /> },
  ];

  return (
    <Card className={className}>
      <CardHeader
        title="Observation"
        subtitle={observation ? `Step ${observation.step}` : undefined}
        icon={<Eye className="w-4 h-4" />}
        action={
          observation && (
            <div className="flex items-center gap-2">
              <Badge variant="info" size="sm">
                {observation.interactableElements?.length ?? 0} elements
              </Badge>
              <Button
                variant="ghost"
                size="sm"
                onClick={() => setShowFullScreen(true)}
              >
                <Maximize2 className="w-4 h-4" />
              </Button>
            </div>
          )
        }
      />
      <CardContent>
        {/* Tabs */}
        <div className="flex border-b border-dark-700 mb-4">
          {tabs.map((tab) => (
            <button
              key={tab.key}
              onClick={() => setActiveTab(tab.key)}
              className={`tab flex items-center gap-1.5 ${
                activeTab === tab.key ? 'tab-active' : ''
              }`}
            >
              {tab.icon}
              {tab.label}
            </button>
          ))}
        </div>

        {isLoading ? (
          <div className="h-48 flex items-center justify-center">
            <Eye className="w-6 h-6 text-dark-500 animate-pulse" />
          </div>
        ) : !observation ? (
          <div className="h-48 flex items-center justify-center text-dark-500">
            <div className="text-center">
              <Eye className="w-8 h-8 mx-auto mb-2 opacity-50" />
              <p>No observation data</p>
            </div>
          </div>
        ) : (
          <div className="min-h-[200px]">
            {/* Page Info */}
            {activeTab === 'page' && (
              <div className="space-y-3">
                <div className="bg-dark-900/50 rounded-lg p-3">
                  <div className="flex items-center gap-2 mb-2">
                    <Globe className="w-4 h-4 text-dark-400" />
                    <a
                      href={observation.page.url}
                      target="_blank"
                      rel="noopener noreferrer"
                      className="text-sm text-accent-primary hover:underline flex items-center gap-1"
                    >
                      {truncateText(observation.page.url, 50)}
                      <ExternalLink className="w-3 h-3" />
                    </a>
                  </div>
                  <div className="text-lg font-medium text-dark-100 mb-2">
                    {observation.page.title || 'Untitled'}
                  </div>
                  <div className="flex flex-wrap gap-2">
                    <Badge variant="neutral" size="sm">
                      {observation.page.domain}
                    </Badge>
                    <Badge
                      variant={
                        observation.page.statusCode < 400 ? 'success' : 'error'
                      }
                      size="sm"
                    >
                      {observation.page.statusCode}
                    </Badge>
                    <Badge variant="info" size="sm">
                      {observation.page.loadTime}ms
                    </Badge>
                  </div>
                </div>

                <div className="bg-dark-900/50 rounded-lg p-3">
                  <div className="text-xs text-dark-400 mb-2">Visible Text</div>
                  <div className="text-sm text-dark-300 max-h-32 overflow-y-auto">
                    {truncateText(observation.visibleText, 500) || 'No text content'}
                  </div>
                </div>

                <div className="flex items-center gap-2 text-xs text-dark-500">
                  <Clock className="w-3 h-3" />
                  <span>{formatTimestamp(observation.timestamp)}</span>
                </div>
              </div>
            )}

            {/* DOM Tree */}
            {activeTab === 'dom' && (
              <div className="bg-dark-900/50 rounded-lg p-3 max-h-[300px] overflow-auto">
                <div className="text-xs text-dark-400 mb-2">
                  {observation.dom?.length ?? 0} root elements
                </div>
                {observation.dom && observation.dom.length > 0 ? (
                  <DOMTree elements={observation.dom} />
                ) : (
                  <div className="text-dark-500 text-sm">No DOM data</div>
                )}
              </div>
            )}

            {/* Extracted Data */}
            {activeTab === 'data' && (
              <div className="space-y-3">
                <div className="bg-dark-900/50 rounded-lg p-3">
                  <div className="text-xs text-dark-400 mb-2">
                    Extracted Data
                  </div>
                  <div className="code-block max-h-[200px] overflow-auto">
                    {Object.keys(observation.extractedData || {}).length > 0
                      ? JSON.stringify(observation.extractedData, null, 2)
                      : '// No extracted data yet'}
                  </div>
                </div>

                <div className="bg-dark-900/50 rounded-lg p-3">
                  <div className="text-xs text-dark-400 mb-2">Metadata</div>
                  <div className="code-block max-h-[100px] overflow-auto">
                    {JSON.stringify(observation.metadata, null, 2)}
                  </div>
                </div>
              </div>
            )}

            {/* Screenshot */}
            {activeTab === 'screenshot' && (
              <div className="bg-dark-900/50 rounded-lg p-3">
                {observation.screenshot ? (
                  <img
                    src={`data:image/png;base64,${observation.screenshot}`}
                    alt="Page screenshot"
                    className="w-full rounded border border-dark-700"
                  />
                ) : (
                  <div className="h-48 flex items-center justify-center text-dark-500">
                    <div className="text-center">
                      <ImageIcon className="w-8 h-8 mx-auto mb-2 opacity-50" />
                      <p>No screenshot available</p>
                    </div>
                  </div>
                )}
              </div>
            )}
          </div>
        )}
      </CardContent>

      {/* Full Screen Modal */}
      {showFullScreen && observation && (
        <div
          className="fixed inset-0 z-50 bg-dark-950/90 flex items-center justify-center p-8"
          onClick={() => setShowFullScreen(false)}
        >
          <div
            className="bg-dark-800 rounded-xl p-6 max-w-4xl max-h-[90vh] overflow-auto"
            onClick={(e) => e.stopPropagation()}
          >
            <div className="flex justify-between items-center mb-4">
              <h2 className="text-xl font-semibold">
                Observation - Step {observation.step}
              </h2>
              <Button variant="ghost" onClick={() => setShowFullScreen(false)}>
                Close
              </Button>
            </div>
            <div className="code-block max-h-[70vh] overflow-auto">
              {JSON.stringify(observation, null, 2)}
            </div>
          </div>
        </div>
      )}
    </Card>
  );
};

export default ObservationView;
