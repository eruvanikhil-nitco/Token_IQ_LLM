(globalThis.TURBOPACK||(globalThis.TURBOPACK=[])).push(["object"==typeof document?document.currentScript:void 0,541071,373488,e=>{"use strict";let t=(0,e.i(475254).default)("ellipsis",[["circle",{cx:"12",cy:"12",r:"1",key:"41hilf"}],["circle",{cx:"19",cy:"12",r:"1",key:"1wjl8i"}],["circle",{cx:"5",cy:"12",r:"1",key:"1pcz8c"}]]);e.s(["default",0,t],373488),e.s(["MoreHorizontal",0,t],541071)},332102,e=>{"use strict";let t=(0,e.i(475254).default)("inbox",[["polyline",{points:"22 12 16 12 14 15 10 15 8 12 2 12",key:"o97t9d"}],["path",{d:"M5.45 5.11 2 12v6a2 2 0 0 0 2 2h16a2 2 0 0 0 2-2v-6l-3.45-6.89A2 2 0 0 0 16.76 4H7.24a2 2 0 0 0-1.79 1.11z",key:"oot6mr"}]]);e.s(["Inbox",0,t],332102)},455037,e=>{"use strict";var t=e.i(494144);e.s(["prism",()=>t.default])},303575,663530,457816,e=>{"use strict";var t=e.i(843476),i=e.i(174886),a=e.i(952571),s=e.i(541071);e.i(707701);var r=e.i(494862);e.i(622826);var n=e.i(997422),o=e.i(112179),l=e.i(487486),d=e.i(519455),p=e.i(755146),m=e.i(196631),c=e.i(500330);let u=e=>e.replace(/^supports_/,"").split("_").map(e=>e.charAt(0).toUpperCase()+e.slice(1)).join(" "),g=e=>Object.entries(e).filter(([e,t])=>e.startsWith("supports_")&&!0===t).map(([e])=>e),x=e=>`$${(1e6*e).toFixed(2)}`,h=e=>e>=1e6?`${(e/1e6).toFixed(1)}M`:e>=1e3?`${(e/1e3).toFixed(1)}K`:e.toString();function _({model:e,onModelClick:r}){return(0,t.jsxs)(p.DropdownMenu,{children:[(0,t.jsx)(p.DropdownMenuTrigger,{"aria-label":"Open model actions","data-testid":`model-hub-actions-${e.model_group}`,className:(0,m.cn)((0,d.buttonVariants)({variant:"ghost",size:"icon-sm"}),"text-muted-foreground"),children:(0,t.jsx)(s.MoreHorizontal,{className:"size-4"})}),(0,t.jsxs)(p.DropdownMenuContent,{align:"end",className:"w-52",children:[(0,t.jsxs)(p.DropdownMenuItem,{"data-testid":"model-hub-action-details",onClick:()=>r(e),children:[(0,t.jsx)(a.Info,{}),"View details"]}),(0,t.jsxs)(p.DropdownMenuItem,{"data-testid":"model-hub-action-copy",onClick:()=>void(0,c.copyToClipboard)(e.model_group,"Model name copied"),children:[(0,t.jsx)(i.Copy,{}),"Copy model name"]})]})]})}e.s(["formatCapabilityName",0,u,"formatCost",0,x,"getModelCapabilities",0,g,"getModelHubTableColumns",0,({onModelClick:e})=>[{id:"model_group",accessorKey:"model_group",meta:{title:"Public Model Name"},header:({column:e})=>(0,t.jsx)(r.DataTableSortHeader,{column:e,title:"Public Model Name"}),size:220,enableSorting:!0,sortingFn:"alphanumeric",cell:({row:i})=>(0,t.jsx)(n.IdentityCell,{title:i.original.model_group,className:"max-w-72",onClick:()=>e(i.original)})},{id:"providers",accessorKey:"providers",meta:{title:"Provider",skeleton:"chips",className:"hidden md:table-cell"},header:({column:e})=>(0,t.jsx)(r.DataTableSortHeader,{column:e,title:"Provider"}),size:150,enableSorting:!0,sortingFn:(e,t)=>e.original.providers.join(", ").localeCompare(t.original.providers.join(", ")),cell:({row:e})=>{let i=e.original.providers;return(0,t.jsxs)("div",{className:"flex flex-wrap gap-1",children:[i.slice(0,2).map(e=>(0,t.jsx)(l.Badge,{variant:"secondary",children:e},e)),i.length>2&&(0,t.jsxs)("span",{className:"text-xs text-muted-foreground",children:["+",i.length-2]})]})}},{id:"mode",accessorKey:"mode",meta:{title:"Mode",className:"hidden lg:table-cell"},header:({column:e})=>(0,t.jsx)(r.DataTableSortHeader,{column:e,title:"Mode"}),size:110,enableSorting:!0,sortingFn:"alphanumeric",cell:({row:e})=>e.original.mode?(0,t.jsx)("span",{className:"font-mono text-xs text-muted-foreground",children:e.original.mode}):(0,t.jsx)("span",{className:"text-xs text-muted-foreground",children:"-"})},{id:"max_input_tokens",accessorKey:"max_input_tokens",meta:{title:"Tokens",className:"hidden lg:table-cell"},header:({column:e})=>(0,t.jsx)(r.DataTableSortHeader,{column:e,title:"Tokens"}),size:110,enableSorting:!0,sortingFn:(e,t)=>(e.original.max_input_tokens||0)+(e.original.max_output_tokens||0)-((t.original.max_input_tokens||0)+(t.original.max_output_tokens||0)),cell:({row:e})=>{let i=e.original;return(0,t.jsxs)("span",{className:"text-xs tabular-nums",children:[i.max_input_tokens?h(i.max_input_tokens):"-"," /"," ",i.max_output_tokens?h(i.max_output_tokens):"-"]})}},{id:"input_cost_per_token",accessorKey:"input_cost_per_token",meta:{title:"Cost/1M",skeleton:"twoLine"},header:({column:e})=>(0,t.jsx)(r.DataTableSortHeader,{column:e,title:"Cost/1M"}),size:110,enableSorting:!0,sortingFn:(e,t)=>(e.original.input_cost_per_token||0)+(e.original.output_cost_per_token||0)-((t.original.input_cost_per_token||0)+(t.original.output_cost_per_token||0)),cell:({row:e})=>{let i=e.original;return(0,t.jsxs)("div",{className:"flex flex-col gap-0.5 text-xs tabular-nums",children:[(0,t.jsx)("span",{children:i.input_cost_per_token?x(i.input_cost_per_token):"-"}),(0,t.jsx)("span",{className:"text-muted-foreground",children:i.output_cost_per_token?x(i.output_cost_per_token):"-"})]})}},{id:"capabilities",meta:{title:"Features",skeleton:"chips"},header:"Features",size:220,enableSorting:!1,cell:({row:e})=>{let i=g(e.original);return 0===i.length?(0,t.jsx)("span",{className:"text-xs text-muted-foreground",children:"-"}):(0,t.jsx)("div",{className:"flex flex-wrap gap-1",children:i.map(e=>(0,t.jsx)(l.Badge,{variant:"outline",children:u(e)},e))})}},{id:"is_public_model_group",accessorKey:"is_public_model_group",meta:{title:"Public",skeleton:"badge",className:"hidden md:table-cell"},header:({column:e})=>(0,t.jsx)(r.DataTableSortHeader,{column:e,title:"Public"}),size:100,enableSorting:!0,sortingFn:(e,t)=>(!0===e.original.is_public_model_group)-(!0===t.original.is_public_model_group),cell:({row:e})=>!0===e.original.is_public_model_group?(0,t.jsx)(o.StatusBadge,{tone:"success",label:"Yes"}):(0,t.jsx)(o.StatusBadge,{tone:"neutral",label:"No"})},{id:"actions",meta:{className:"text-right",headerClassName:"text-right"},header:()=>(0,t.jsx)("span",{className:"sr-only",children:"Actions"}),size:64,enableSorting:!1,enableHiding:!1,cell:({row:i})=>(0,t.jsx)("div",{className:"flex justify-end",children:(0,t.jsx)(_,{model:i.original,onModelClick:e})})}]],303575);var f=e.i(602869),b=e.i(776639),j=e.i(650056),y=e.i(455037),N=e.i(488012);e.s(["default",0,({selectedModel:e,onClose:i})=>{let a,s=(0,N.useSyntaxTheme)(y.prism);return(0,t.jsx)(b.Dialog,{open:null!==e,onOpenChange:e=>!e&&i(),children:(0,t.jsxs)(b.DialogContent,{className:"max-h-[calc(100dvh-2rem)] overflow-y-auto sm:max-w-[1000px]",children:[(0,t.jsx)(b.DialogHeader,{children:(0,t.jsx)(b.DialogTitle,{children:e?.model_group||"Model Details"})}),e&&(0,t.jsxs)("div",{className:"space-y-6",children:[(0,t.jsxs)("div",{children:[(0,t.jsx)("p",{className:"text-lg font-semibold mb-4",children:"Model Overview"}),(0,t.jsxs)("div",{className:"grid grid-cols-2 gap-4 mb-4",children:[(0,t.jsxs)("div",{children:[(0,t.jsx)("p",{className:"font-medium",children:"Model Group:"}),(0,t.jsx)("p",{children:e.model_group})]}),(0,t.jsxs)("div",{children:[(0,t.jsx)("p",{className:"font-medium",children:"Mode:"}),(0,t.jsx)("p",{children:e.mode||"Not specified"})]}),(0,t.jsxs)("div",{children:[(0,t.jsx)("p",{className:"font-medium",children:"Providers:"}),(0,t.jsx)("div",{className:"flex flex-wrap gap-1 mt-1",children:e.providers.map(e=>(0,t.jsx)(l.Badge,{variant:"secondary",children:e},e))})]})]})]}),(0,t.jsxs)("div",{children:[(0,t.jsx)("p",{className:"text-lg font-semibold mb-4",children:"Token & Cost Information"}),(0,t.jsxs)("div",{className:"grid grid-cols-2 gap-4",children:[(0,t.jsxs)("div",{children:[(0,t.jsx)("p",{className:"font-medium",children:"Max Input Tokens:"}),(0,t.jsx)("p",{children:e.max_input_tokens?.toLocaleString()||"Not specified"})]}),(0,t.jsxs)("div",{children:[(0,t.jsx)("p",{className:"font-medium",children:"Max Output Tokens:"}),(0,t.jsx)("p",{children:e.max_output_tokens?.toLocaleString()||"Not specified"})]}),(0,t.jsxs)("div",{children:[(0,t.jsx)("p",{className:"font-medium",children:"Input Cost per 1M Tokens:"}),(0,t.jsx)("p",{children:e.input_cost_per_token?x(e.input_cost_per_token):"Not specified"})]}),(0,t.jsxs)("div",{children:[(0,t.jsx)("p",{className:"font-medium",children:"Output Cost per 1M Tokens:"}),(0,t.jsx)("p",{children:e.output_cost_per_token?x(e.output_cost_per_token):"Not specified"})]})]})]}),(0,t.jsxs)("div",{children:[(0,t.jsx)("p",{className:"text-lg font-semibold mb-4",children:"Capabilities"}),(0,t.jsx)("div",{className:"flex flex-wrap gap-2",children:0===(a=g(e)).length?(0,t.jsx)("p",{className:"text-muted-foreground",children:"No special capabilities listed"}):a.map((e,i)=>(0,t.jsx)(l.Badge,{variant:"secondary",children:u(e)},e))})]}),(e.tpm||e.rpm)&&(0,t.jsxs)("div",{children:[(0,t.jsx)("p",{className:"text-lg font-semibold mb-4",children:"Rate Limits"}),(0,t.jsxs)("div",{className:"grid grid-cols-2 gap-4",children:[e.tpm&&(0,t.jsxs)("div",{children:[(0,t.jsx)("p",{className:"font-medium",children:"Tokens per Minute:"}),(0,t.jsx)("p",{children:e.tpm.toLocaleString()})]}),e.rpm&&(0,t.jsxs)("div",{children:[(0,t.jsx)("p",{className:"font-medium",children:"Requests per Minute:"}),(0,t.jsx)("p",{children:e.rpm.toLocaleString()})]})]})]}),e.supported_openai_params&&(0,t.jsxs)("div",{children:[(0,t.jsx)("p",{className:"text-lg font-semibold mb-4",children:"Supported OpenAI Parameters"}),(0,t.jsx)("div",{className:"flex flex-wrap gap-2",children:e.supported_openai_params.map(e=>(0,t.jsx)(l.Badge,{variant:"default",children:e},e))})]}),(0,t.jsxs)("div",{children:[(0,t.jsx)("p",{className:"text-lg font-semibold mb-4",children:"Usage Example"}),(0,t.jsx)(j.Prism,{language:"python",className:"text-sm",style:s,children:`import openai

client = openai.OpenAI(
    api_key="your_api_key",
    base_url="${(0,f.getProxyBaseUrl)()}"  # Your Token IQ URL
)

response = client.chat.completions.create(
    model="${e.model_group}",
    messages=[
        {
            "role": "user",
            "content": "Hello, how are you?"
        }
    ]
)

print(response.choices[0].message.content)`})]})]})]})})}],663530);let v=e=>!0===e.is_observed_only;e.s(["filterModelsByVisibleProviders",0,(e,t)=>{if(void 0===t)return e;let i=new Set(t);return e.filter(e=>v(e)||(e.providers??[]).some(e=>i.has(e)))},"isObservedOnly",0,v],457816)},306228,e=>{"use strict";let t=(0,e.i(475254).default)("link-2",[["path",{d:"M9 17H7A5 5 0 0 1 7 7h2",key:"8i5ue5"}],["path",{d:"M15 7h2a5 5 0 1 1 0 10h-2",key:"1b9ql8"}],["line",{x1:"8",x2:"16",y1:"12",y2:"12",key:"1jonct"}]]);e.s(["Link2",0,t],306228)},909947,865361,e=>{"use strict";var t,i,a=((t={}).AUDIO_SPEECH="audio_speech",t.AUDIO_TRANSCRIPTION="audio_transcription",t.IMAGE_GENERATION="image_generation",t.VIDEO_GENERATION="video_generation",t.CHAT="chat",t.COMPLETION="completion",t.RESPONSES="responses",t.IMAGE_EDITS="image_edit",t.ANTHROPIC_MESSAGES="anthropic_messages",t.EMBEDDING="embedding",t.REALTIME="realtime",t),s=((i={}).IMAGE="image",i.VIDEO="video",i.CHAT="chat",i.RESPONSES="responses",i.IMAGE_EDITS="image_edits",i.ANTHROPIC_MESSAGES="anthropic_messages",i.EMBEDDINGS="embeddings",i.SPEECH="speech",i.TRANSCRIPTION="transcription",i.A2A_AGENTS="a2a_agents",i.MCP="mcp",i.REALTIME="realtime",i.INTERACTIONS="interactions",i);let r={image_generation:"image",video_generation:"video",chat:"chat",completion:"chat",responses:"responses",image_edit:"image_edits",anthropic_messages:"anthropic_messages",audio_speech:"speech",audio_transcription:"transcription",embedding:"embeddings",realtime:"realtime"};e.s(["EndpointType",()=>s,"ModelMode",()=>a,"getEndpointType",0,e=>Object.values(a).includes(e)?r[e]:"chat"],865361),e.s(["generateCodeSnippet",0,e=>{let t,{apiKeySource:i,accessToken:a,apiKey:r,inputMessage:n,chatHistory:o,selectedTags:l,selectedVectorStores:d,selectedGuardrails:p,selectedPolicies:m,selectedVoice:c,endpointType:u,selectedModel:g,selectedSdk:x,proxySettings:h}=e,_="session"===i?a:r,f=window.location.origin,b=h?.LITELLM_UI_API_DOC_BASE_URL;b&&b.trim()?f=b:h?.PROXY_BASE_URL&&(f=h.PROXY_BASE_URL);let j=n||"Your prompt here",y=j.replace(/\\/g,"\\\\").replace(/"/g,'\\"').replace(/\n/g,"\\n"),N=o.filter(e=>!e.isImage).map(({role:e,content:t})=>({role:e,content:t})),v={};l.length>0&&(v.tags=l),d.length>0&&(v.vector_stores=d),p.length>0&&(v.guardrails=p),m.length>0&&(v.policies=m);let k=g||"your-model-name",w="azure"===x?`import openai

client = openai.AzureOpenAI(
	api_key="${_||"YOUR_LITELLM_API_KEY"}",
	azure_endpoint="${f}",
	api_version="2024-02-01"
)`:`import openai

client = openai.OpenAI(
	api_key="${_||"YOUR_LITELLM_API_KEY"}",
	base_url="${f}"
)`;switch(u){case s.CHAT:{let e=Object.keys(v).length>0,i="";if(e){let e=JSON.stringify({metadata:v},null,2).split("\n").map(e=>" ".repeat(4)+e).join("\n").trim();i=`,
    extra_body=${e}`}let a=N.length>0?N:[{role:"user",content:j}];t=`
import base64

# Helper function to encode images to base64
def encode_image(image_path):
    with open(image_path, "rb") as image_file:
        return base64.b64encode(image_file.read()).decode('utf-8')

# Example with text only
response = client.chat.completions.create(
    model="${k}",
    messages=${JSON.stringify(a,null,4)}${i}
)

print(response)

# Example with image or PDF (uncomment and provide file path to use)
# base64_file = encode_image("path/to/your/file.jpg")  # or .pdf
# response_with_file = client.chat.completions.create(
#     model="${k}",
#     messages=[
#         {
#             "role": "user",
#             "content": [
#                 {
#                     "type": "text",
#                     "text": "${y}"
#                 },
#                 {
#                     "type": "image_url",
#                     "image_url": {
#                         "url": f"data:image/jpeg;base64,{base64_file}"  # or data:application/pdf;base64,{base64_file}
#                     }
#                 }
#             ]
#         }
#     ]${i}
# )
# print(response_with_file)
`;break}case s.RESPONSES:{let e=Object.keys(v).length>0,i="";if(e){let e=JSON.stringify({metadata:v},null,2).split("\n").map(e=>" ".repeat(4)+e).join("\n").trim();i=`,
    extra_body=${e}`}let a=N.length>0?N:[{role:"user",content:j}];t=`
import base64

# Helper function to encode images to base64
def encode_image(image_path):
    with open(image_path, "rb") as image_file:
        return base64.b64encode(image_file.read()).decode('utf-8')

# Example with text only
response = client.responses.create(
    model="${k}",
    input=${JSON.stringify(a,null,4)}${i}
)

print(response.output_text)

# Example with image or PDF (uncomment and provide file path to use)
# base64_file = encode_image("path/to/your/file.jpg")  # or .pdf
# response_with_file = client.responses.create(
#     model="${k}",
#     input=[
#         {
#             "role": "user",
#             "content": [
#                 {"type": "input_text", "text": "${y}"},
#                 {
#                     "type": "input_image",
#                     "image_url": f"data:image/jpeg;base64,{base64_file}",  # or data:application/pdf;base64,{base64_file}
#                 },
#             ],
#         }
#     ]${i}
# )
# print(response_with_file.output_text)
`;break}case s.IMAGE:t="azure"===x?`
# NOTE: The Azure SDK does not have a direct equivalent to the multi-modal 'responses.create' method shown for OpenAI.
# This snippet uses 'client.images.generate' and will create a new image based on your prompt.
# It does not use the uploaded image, as 'client.images.generate' does not support image inputs in this context.
import os
import requests
import json
import time
from PIL import Image

result = client.images.generate(
	model="${k}",
	prompt="${n}",
	n=1
)

json_response = json.loads(result.model_dump_json())

# Set the directory for the stored image
image_dir = os.path.join(os.curdir, 'images')

# If the directory doesn't exist, create it
if not os.path.isdir(image_dir):
	os.mkdir(image_dir)

# Initialize the image path
image_filename = f"generated_image_{int(time.time())}.png"
image_path = os.path.join(image_dir, image_filename)

try:
	# Retrieve the generated image
	if json_response.get("data") && len(json_response["data"]) > 0 && json_response["data"][0].get("url"):
			image_url = json_response["data"][0]["url"]
			generated_image = requests.get(image_url).content
			with open(image_path, "wb") as image_file:
					image_file.write(generated_image)

			print(f"Image saved to {image_path}")
			# Display the image
			image = Image.open(image_path)
			image.show()
	else:
			print("Could not find image URL in response.")
			print("Full response:", json_response)
except Exception as e:
	print(f"An error occurred: {e}")
	print("Full response:", json_response)
`:`
import base64
import os
import time
import json
from PIL import Image
import requests

# Helper function to encode images to base64
def encode_image(image_path):
	with open(image_path, "rb") as image_file:
			return base64.b64encode(image_file.read()).decode('utf-8')

# Helper function to create a file (simplified for this example)
def create_file(image_path):
	# In a real implementation, this would upload the file to OpenAI
	# For this example, we'll just return a placeholder ID
	return f"file_{os.path.basename(image_path).replace('.', '_')}"

# The prompt entered by the user
prompt = "${y}"

# Encode images to base64
base64_image1 = encode_image("body-lotion.png")
base64_image2 = encode_image("soap.png")

# Create file IDs
file_id1 = create_file("body-lotion.png")
file_id2 = create_file("incense-kit.png")

response = client.responses.create(
	model="${k}",
	input=[
			{
					"role": "user",
					"content": [
							{"type": "input_text", "text": prompt},
							{
									"type": "input_image",
									"image_url": f"data:image/jpeg;base64,{base64_image1}",
							},
							{
									"type": "input_image",
									"image_url": f"data:image/jpeg;base64,{base64_image2}",
							},
							{
									"type": "input_image",
									"file_id": file_id1,
							},
							{
									"type": "input_image",
									"file_id": file_id2,
							}
					],
			}
	],
	tools=[{"type": "image_generation"}],
)

# Process the response
image_generation_calls = [
	output
	for output in response.output
	if output.type == "image_generation_call"
]

image_data = [output.result for output in image_generation_calls]

if image_data:
	image_base64 = image_data[0]
	image_filename = f"edited_image_{int(time.time())}.png"
	with open(image_filename, "wb") as f:
			f.write(base64.b64decode(image_base64))
	print(f"Image saved to {image_filename}")
else:
	# If no image is generated, there might be a text response with an explanation
	text_response = [output.text for output in response.output if hasattr(output, 'text')]
	if text_response:
			print("No image generated. Model response:")
			print("\\n".join(text_response))
	else:
			print("No image data found in response.")
	print("Full response for debugging:")
	print(response)
`;break;case s.IMAGE_EDITS:t="azure"===x?`
import base64
import os
import time
import json
from PIL import Image
import requests

# Helper function to encode images to base64
def encode_image(image_path):
	with open(image_path, "rb") as image_file:
			return base64.b64encode(image_file.read()).decode('utf-8')

# The prompt entered by the user
prompt = "${y}"

# Encode images to base64
base64_image1 = encode_image("body-lotion.png")
base64_image2 = encode_image("soap.png")

# Create file IDs
file_id1 = create_file("body-lotion.png")
file_id2 = create_file("incense-kit.png")

response = client.responses.create(
	model="${k}",
	input=[
			{
					"role": "user",
					"content": [
							{"type": "input_text", "text": prompt},
							{
									"type": "input_image",
									"image_url": f"data:image/jpeg;base64,{base64_image1}",
							},
							{
									"type": "input_image",
									"image_url": f"data:image/jpeg;base64,{base64_image2}",
							},
							{
									"type": "input_image",
									"file_id": file_id1,
							},
							{
									"type": "input_image",
									"file_id": file_id2,
							}
					],
			}
	],
	tools=[{"type": "image_generation"}],
)

# Process the response
image_generation_calls = [
	output
	for output in response.output
	if output.type == "image_generation_call"
]

image_data = [output.result for output in image_generation_calls]

if image_data:
	image_base64 = image_data[0]
	image_filename = f"edited_image_{int(time.time())}.png"
	with open(image_filename, "wb") as f:
			f.write(base64.b64decode(image_base64))
	print(f"Image saved to {image_filename}")
else:
	# If no image is generated, there might be a text response with an explanation
	text_response = [output.text for output in response.output if hasattr(output, 'text')]
	if text_response:
			print("No image generated. Model response:")
			print("\\n".join(text_response))
	else:
			print("No image data found in response.")
	print("Full response for debugging:")
	print(response)
`:`
import base64
import os
import time

# Helper function to encode images to base64
def encode_image(image_path):
	with open(image_path, "rb") as image_file:
			return base64.b64encode(image_file.read()).decode('utf-8')

# Helper function to create a file (simplified for this example)
def create_file(image_path):
	# In a real implementation, this would upload the file to OpenAI
	# For this example, we'll just return a placeholder ID
	return f"file_{os.path.basename(image_path).replace('.', '_')}"

# The prompt entered by the user
prompt = "${y}"

# Encode images to base64
base64_image1 = encode_image("body-lotion.png")
base64_image2 = encode_image("soap.png")

# Create file IDs
file_id1 = create_file("body-lotion.png")
file_id2 = create_file("incense-kit.png")

response = client.responses.create(
	model="${k}",
	input=[
			{
					"role": "user",
					"content": [
							{"type": "input_text", "text": prompt},
							{
									"type": "input_image",
									"image_url": f"data:image/jpeg;base64,{base64_image1}",
							},
							{
									"type": "input_image",
									"image_url": f"data:image/jpeg;base64,{base64_image2}",
							},
							{
									"type": "input_image",
									"file_id": file_id1,
							},
							{
									"type": "input_image",
									"file_id": file_id2,
							}
					],
			}
	],
	tools=[{"type": "image_generation"}],
)

# Process the response
image_generation_calls = [
	output
	for output in response.output
	if output.type == "image_generation_call"
]

image_data = [output.result for output in image_generation_calls]

if image_data:
	image_base64 = image_data[0]
	image_filename = f"edited_image_{int(time.time())}.png"
	with open(image_filename, "wb") as f:
			f.write(base64.b64decode(image_base64))
	print(f"Image saved to {image_filename}")
else:
	# If no image is generated, there might be a text response with an explanation
	text_response = [output.text for output in response.output if hasattr(output, 'text')]
	if text_response:
			print("No image generated. Model response:")
			print("\\n".join(text_response))
	else:
			print("No image data found in response.")
	print("Full response for debugging:")
	print(response)
`;break;case s.EMBEDDINGS:t=`
response = client.embeddings.create(
	input="${n||"Your string here"}",
	model="${k}",
	encoding_format="base64" # or "float"
)

print(response.data[0].embedding)
`;break;case s.TRANSCRIPTION:t=`
# Open the audio file
audio_file = open("path/to/your/audio/file.mp3", "rb")

# Make the transcription request
response = client.audio.transcriptions.create(
	model="${k}",
	file=audio_file${n?`,
	prompt="${n.replace(/\\/g,"\\\\").replace(/"/g,'\\"')}"`:""}
)

print(response.text)
`;break;case s.SPEECH:t=`
# Make the text-to-speech request
response = client.audio.speech.create(
	model="${k}",
	input="${n||"Your text to convert to speech here"}",
	voice="${c}"  # Options: alloy, ash, ballad, coral, echo, fable, nova, onyx, sage, shimmer
)

# Save the audio to a file
output_filename = "output_speech.mp3"
response.stream_to_file(output_filename)
print(f"Audio saved to {output_filename}")

# Optional: Customize response format and speed
# response = client.audio.speech.create(
#     model="${k}",
#     input="${n||"Your text to convert to speech here"}",
#     voice="alloy",
#     response_format="mp3",  # Options: mp3, opus, aac, flac, wav, pcm
#     speed=1.0  # Range: 0.25 to 4.0
# )
# response.stream_to_file("output_speech.mp3")
`;break;default:t="\n# Code generation for this endpoint is not implemented yet."}return`${w}
${t}`}],909947)},899426,e=>{"use strict";let t=e=>e.trim().toLowerCase();function i(e,i){let a=t(e);if(""===a)return!0;let s=i.filter(e=>"string"==typeof e).map(e=>e.toLowerCase());return!!s.some(e=>e.includes(a))||a.split(/\s+/).every(e=>s.some(t=>t.includes(e)))}e.s(["filterBySearchTerm",0,function(e,t,a){return e.filter(e=>i(t,a(e)))},"matchesSearchTerm",0,i,"rankBySearchRelevance",0,function(e,i,a){let s=t(i);if(""===s)return[...e];let r=e=>{let t=a(e).toLowerCase();return 1e3*(t===s)+100*!!t.startsWith(s)+(1e3-t.length)};return[...e].sort((e,t)=>r(t)-r(e))}])},652272,209261,e=>{"use strict";var t=e.i(843476),i=e.i(271645),a=e.i(871689),s=e.i(643531),r=e.i(174886),n=e.i(306228),o=e.i(196631);let l=/^[a-zA-Z0-9][a-zA-Z0-9._-]*(\/[a-zA-Z0-9][a-zA-Z0-9._-]*)*$/,d=e=>e.trim().replace(/\/+$/,""),p=/\.(md|markdown|txt|json|ya?ml|toml)$/i,m=/^\d{1,3}(\.\d{1,3}){3}$/,c=/^[A-Za-z0-9-]+$/,u=/^[A-Za-z0-9._-]+$/,g=e=>e.pathname.split("/").filter(e=>""!==e),x=e=>{let t=e.split("/").filter(e=>""!==e);return t[t.length-1]??""},h=e=>e.toLowerCase().replace(/[^a-z0-9-]+/g,"-").replace(/-+/g,"-").replace(/^-+|-+$/g,""),_=e=>JSON.stringify({extraKnownMarketplaces:{litellm:{source:{source:"url",url:`${e}/claude-code/marketplace.json`}}}},null,2),f=e=>`/plugin install ${e.name}@litellm`;e.s(["buildMarketplaceSettingsSnippet",0,_,"formatInstallCommand",0,f,"getCategoryBadgeColor",0,e=>{if(!e)return"gray";let t=e.toLowerCase();if(t.includes("development")||t.includes("dev"))return"blue";if(t.includes("productivity")||t.includes("workflow"))return"green";if(t.includes("learning")||t.includes("education"))return"purple";if(t.includes("security")||t.includes("safety"))return"red";if(t.includes("data")||t.includes("analytics"))return"orange";else if(t.includes("integration")||t.includes("api"))return"yellow";return"gray"},"isValidEmail",0,e=>!e||/^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(e),"isValidSemanticVersion",0,e=>!e||/^\d+\.\d+\.\d+(-[a-zA-Z0-9.-]+)?(\+[a-zA-Z0-9.-]+)?$/.test(e),"isValidSubPath",0,e=>{let t=d(e);return""!==t&&l.test(t)},"parseKeywords",0,e=>e&&""!==e.trim()?e.split(",").map(e=>e.trim()).filter(e=>""!==e):[],"parseSkillSource",0,(e,t)=>{let i=(e=>{let t,i=e.trim();if(""===i||i.startsWith("//"))return null;let a=/^[a-z][a-z0-9+.-]*:\/\//i.test(i)?i:`https://${i}`;try{t=new URL(a)}catch{return null}return"https:"!==t.protocol||""!==t.username||""!==t.password||!t.hostname.includes(".")||t.hostname.startsWith("[")||m.test(t.hostname)?null:t})(e);if(!i)return null;if("github.com"===i.hostname.replace(/^www\./,""))return((e,t)=>{let i=g(e);if(i.length<2)return null;let a=i[0],s=i[1].replace(/\.git$/,"");if(!c.test(a)||!u.test(s))return null;let r=`${a}/${s}`,n=`https://github.com/${r}`,o={parsed:{source:"github",repo:r},label:`GitHub repo — ${r}`,suggestedName:h(s)};if(i.length>=4&&("tree"===i[2]||"blob"===i[2])){let e=i.slice(4),t=x(e.join("/")),a=p.test(t)?e.slice(0,-1):e;if(0===a.length)return o;let s=d(a.join("/"));return l.test(s)?{parsed:{source:"git-subdir",url:n,path:s},label:`GitHub subdir — ${r} @ ${s}`,suggestedName:h(x(s))}:null}if(2!==i.length)return null;let m=d(t??"");return""!==m?l.test(m)?{parsed:{source:"git-subdir",url:n,path:m},label:`GitHub subdir — ${r} @ ${m}`,suggestedName:h(x(m))}:null:o})(i,t);if(g(i).length<2)return null;let a=`${i.protocol}//${i.host}${i.pathname.replace(/\/+$/,"")}`,s=d(t??"");return""!==s?l.test(s)?{parsed:{source:"git-subdir",url:a,path:s},label:`Git subdir — ${a} @ ${s}`,suggestedName:h(x(s))}:null:{parsed:{source:"url",url:a},label:`Git repo — ${a}`,suggestedName:h(x(i.pathname).replace(/\.git$/,""))}},"validatePluginName",0,e=>!!e&&""!==e.trim()&&/^[a-z0-9-]+$/.test(e)],209261),e.s(["default",0,({skill:e,onBack:l})=>{let d,[p,m]=(0,i.useState)("overview"),[c,u]=(0,i.useState)(null),g=(e,t)=>{navigator.clipboard.writeText(e),u(t),setTimeout(()=>u(null),2e3)},x="github"===(d=e.source).source&&d.repo?`https://github.com/${d.repo}`:"git-subdir"===d.source&&d.url?d.path?`${d.url}/tree/main/${d.path}`:d.url:"url"===d.source&&d.url?d.url:null,h=f(e),b=_(window.location.origin),j=[...e.category?[{property:"Category",value:e.category}]:[],...e.domain?[{property:"Domain",value:e.domain}]:[],...e.namespace?[{property:"Namespace",value:e.namespace}]:[],...e.version?[{property:"Version",value:e.version}]:[],...e.author?.name?[{property:"Author",value:e.author.name}]:[],...e.created_at?[{property:"Added",value:new Date(e.created_at).toLocaleDateString()}]:[]];return(0,t.jsxs)("div",{className:"py-6 pl-0 pr-8",children:[(0,t.jsxs)("div",{onClick:l,className:"mb-6 inline-flex cursor-pointer items-center gap-1.5 text-sm text-muted-foreground",children:[(0,t.jsx)(a.ArrowLeft,{className:"size-3"}),(0,t.jsx)("span",{children:"Skills"})]}),(0,t.jsxs)("div",{className:"mb-2",children:[(0,t.jsx)("h1",{className:"m-0 text-[28px] font-normal leading-tight text-foreground",children:e.name}),e.description&&(0,t.jsx)("p",{className:"mb-0 ml-0 mr-0 mt-2 text-sm leading-relaxed text-muted-foreground",children:e.description})]}),(0,t.jsx)("div",{className:"mb-7 mt-6 border-b border-border",children:(0,t.jsx)("div",{className:"flex",children:[{key:"overview",label:"Overview"},{key:"usage",label:"How to Use"}].map(e=>(0,t.jsx)("div",{onClick:()=>m(e.key),className:(0,o.cn)("-mb-px cursor-pointer border-b-[3px] px-5 py-3 text-sm",p===e.key?"border-info font-medium text-info":"border-transparent font-normal text-muted-foreground"),children:e.label},e.key))})}),"overview"===p&&(0,t.jsxs)("div",{className:"flex gap-16",children:[(0,t.jsxs)("div",{className:"min-w-0 flex-1",children:[(0,t.jsx)("h2",{className:"m-0 mb-1 text-lg font-normal text-foreground",children:"Skill Details"}),(0,t.jsx)("p",{className:"m-0 mb-4 text-[13px] text-muted-foreground",children:"Metadata registered with this skill"}),(0,t.jsxs)("table",{className:"w-full border-collapse text-sm",children:[(0,t.jsx)("thead",{children:(0,t.jsxs)("tr",{className:"border-b border-border",children:[(0,t.jsx)("th",{className:"w-40 py-3 text-left font-medium text-muted-foreground",children:"Property"}),(0,t.jsx)("th",{className:"py-3 text-left font-medium text-muted-foreground",children:e.name})]})}),(0,t.jsx)("tbody",{children:j.map((e,i)=>(0,t.jsxs)("tr",{className:"border-b border-border",children:[(0,t.jsx)("td",{className:"py-3 text-foreground",children:e.property}),(0,t.jsx)("td",{className:"py-3 text-foreground",children:e.value})]},i))})]})]}),(0,t.jsxs)("div",{className:"w-60 shrink-0",children:[(0,t.jsxs)("div",{className:"mb-6",children:[(0,t.jsx)("div",{className:"mb-1 text-xs text-muted-foreground",children:"Status"}),(0,t.jsx)("span",{className:(0,o.cn)("rounded-xl px-2.5 py-[3px] text-xs font-medium",e.enabled?"bg-success/10 text-success":"bg-muted text-muted-foreground"),children:e.enabled?"Public":"Draft"})]}),x&&(0,t.jsxs)("div",{className:"mb-6",children:[(0,t.jsx)("div",{className:"mb-1 text-xs text-muted-foreground",children:"Source"}),(0,t.jsxs)("a",{href:x,target:"_blank",rel:"noopener noreferrer",className:"flex items-center gap-1 break-all text-[13px] text-info",children:[x.replace("https://",""),(0,t.jsx)(n.Link2,{className:"size-3 shrink-0"})]})]}),e.keywords&&e.keywords.length>0&&(0,t.jsxs)("div",{className:"mb-6",children:[(0,t.jsx)("div",{className:"mb-2 text-xs text-muted-foreground",children:"Tags"}),(0,t.jsx)("div",{className:"flex flex-wrap gap-1.5",children:e.keywords.map(e=>(0,t.jsx)("span",{className:"rounded-2xl border border-border bg-card px-3 py-1 text-xs text-foreground",children:e},e))})]}),(0,t.jsxs)("div",{children:[(0,t.jsx)("div",{className:"mb-1 text-xs text-muted-foreground",children:"Skill ID"}),(0,t.jsx)("div",{className:"break-all font-mono text-xs text-foreground",children:e.id})]})]})]}),"usage"===p&&(0,t.jsxs)("div",{className:"max-w-[640px]",children:[(0,t.jsx)("h2",{className:"m-0 mb-2 text-lg font-normal text-foreground",children:"Using this skill"}),(0,t.jsx)("p",{className:"m-0 mb-6 text-sm leading-relaxed text-muted-foreground",children:"Once your proxy is set as a marketplace, enable this skill in Claude Code with one command:"}),(0,t.jsxs)("div",{className:"mb-6 overflow-hidden rounded-lg border border-border",children:[(0,t.jsxs)("div",{className:"flex items-center justify-between border-b border-border bg-muted px-4 py-2.5",children:[(0,t.jsx)("span",{className:"text-[13px] font-medium text-foreground",children:"Run in Claude Code"}),(0,t.jsxs)("button",{onClick:()=>g(h,"install"),className:(0,o.cn)("flex cursor-pointer items-center gap-1 border-none bg-transparent p-0 text-xs","install"===c?"text-success":"text-info"),children:["install"===c?(0,t.jsx)(s.Check,{className:"size-3"}):(0,t.jsx)(r.Copy,{className:"size-3"}),"install"===c?"Copied":"Copy"]})]}),(0,t.jsx)("pre",{className:"m-0 bg-card px-4 py-3.5 font-mono text-sm text-foreground",children:h})]}),(0,t.jsxs)("div",{className:"mb-4 rounded-lg border border-warning/30 bg-warning/10 px-4 py-3",children:[(0,t.jsxs)("p",{className:"m-0 mb-2 text-[13px] leading-relaxed text-muted-foreground",children:['If you see "Plugin ',e.name,'not found in marketplace", update the catalog first:']}),(0,t.jsx)("pre",{className:"m-0 bg-transparent font-mono text-[13px] text-foreground",children:"/plugin marketplace update litellm"})]}),(0,t.jsxs)("p",{className:"m-0 text-[13px] leading-relaxed text-muted-foreground",children:["Don't have the marketplace configured yet?"," ",(0,t.jsx)("span",{onClick:()=>m("setup"),className:"cursor-pointer text-info",children:"See one-time setup →"})]})]}),"setup"===p&&(0,t.jsxs)("div",{className:"max-w-[640px]",children:[(0,t.jsx)("h2",{className:"m-0 mb-2 text-lg font-normal text-foreground",children:"One-time marketplace setup"}),(0,t.jsx)("p",{className:"m-0 mb-3 text-sm leading-relaxed text-muted-foreground",children:"Run this command in Claude Code to register the marketplace:"}),(0,t.jsxs)("div",{className:"mb-6 overflow-hidden rounded-lg border border-border",children:[(0,t.jsxs)("div",{className:"flex items-center justify-between border-b border-border bg-muted px-4 py-2.5",children:[(0,t.jsx)("span",{className:"text-[13px] font-medium text-foreground",children:"Run in Claude Code"}),(0,t.jsxs)("button",{onClick:()=>{let e=window.location.origin;g(`/plugin marketplace add ${e}/claude-code/marketplace.json`,"marketplace-cmd")},className:(0,o.cn)("flex cursor-pointer items-center gap-1 border-none bg-transparent p-0 text-xs","marketplace-cmd"===c?"text-success":"text-info"),children:["marketplace-cmd"===c?(0,t.jsx)(s.Check,{className:"size-3"}):(0,t.jsx)(r.Copy,{className:"size-3"}),"marketplace-cmd"===c?"Copied":"Copy"]})]}),(0,t.jsx)("pre",{className:"m-0 bg-card px-4 py-3.5 font-mono text-[13px] text-foreground",children:`/plugin marketplace add ${window.location.origin}/claude-code/marketplace.json`})]}),(0,t.jsxs)("p",{className:"m-0 mb-3 text-sm leading-relaxed text-muted-foreground",children:["Or add this to ",(0,t.jsx)("code",{className:"rounded bg-muted px-1.5 py-px text-[13px]",children:"~/.claude/settings.json"})," ","for a persistent configuration:"]}),(0,t.jsxs)("div",{className:"overflow-hidden rounded-lg border border-border",children:[(0,t.jsxs)("div",{className:"flex items-center justify-between border-b border-border bg-muted px-4 py-2.5",children:[(0,t.jsx)("span",{className:"text-[13px] font-medium text-foreground",children:"~/.claude/settings.json"}),(0,t.jsxs)("button",{onClick:()=>g(b,"settings"),className:(0,o.cn)("flex cursor-pointer items-center gap-1 border-none bg-transparent p-0 text-xs","settings"===c?"text-success":"text-info"),children:["settings"===c?(0,t.jsx)(s.Check,{className:"size-3"}):(0,t.jsx)(r.Copy,{className:"size-3"}),"settings"===c?"Copied":"Copy"]})]}),(0,t.jsx)("pre",{className:"m-0 bg-card px-4 py-3.5 font-mono text-[13px] text-foreground",children:b})]})]})]})}],652272)},157058,e=>{"use strict";var t=e.i(843476),i=e.i(934879),a=e.i(976883),s=e.i(135214),r=e.i(708347);e.s(["default",0,function(){let{accessToken:e,userRole:n,premiumUser:o}=(0,s.default)();return(0,r.isAdminRole)(n)?(0,t.jsx)(i.default,{accessToken:e,publicPage:!1,premiumUser:o,userRole:n}):(0,t.jsx)(a.default,{accessToken:e,isEmbedded:!0})}])}]);